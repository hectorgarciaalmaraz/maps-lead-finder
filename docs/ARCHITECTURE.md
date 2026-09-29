# Architecture

This document describes how Maps Lead Finder is put together: what each module owns, how data moves from a Google Places search to a sent message, and where to extend it. The README covers setup and limitations.

## Layers

```text
Entry points     main.py (Click CLI)            dashboard.py → skills/dashboard/app.py (Flask)
                        │                                      │
Orchestration    tools/*.py                                    │  (route handlers call skills/ directly)
                        │                                      │
Domain           skills/scraping   skills/proposals   skills/contact
                        │                  │                 │
Persistence      SQLite via Flask-SQLAlchemy models in skills/dashboard/app.py
Configuration    config/__init__.py (AppConfig) ← .env + config/settings.yaml + config/services_catalog.yaml
```

- **Entry points** parse input and print results. The CLI never talks to Google, Anthropic or Twilio directly.
- **`tools/`** holds one function per CLI workflow. Each creates the Flask app to get a database session, loops over prospects or proposals, calls the domain classes, and returns a summary `dict`.
- **`skills/`** holds the domain logic. Classes receive their configuration and database session as arguments, which is what makes them testable with mocks and an in-memory SQLite database.
- **`config`** builds a single `AppConfig` object at import time. It loads secrets from `config/.env` (or `.env` in the root) and tunables from `settings.yaml`. If loading fails, `config` is `None` and a warning is raised; entry points then fail with a clear message.

## Modules

| Module | Responsibility |
|---|---|
| `config/__init__.py` | `AppConfig` dataclass tree (`ScrapingConfig`, `ProposalsConfig`, `ContactConfig`, `AgencyContactInfo`), env loading, logging setup |
| `skills/scraping/google_maps.py` | `GoogleMapsScraper`: Nearby Search per category with pagination, Place Details per result, category mapping, haversine distance, save with `place_id` dedup |
| `skills/scraping/data_enrichment.py` | `DataEnricher`: fetch homepage/contact page, extract email and social links, filter system emails, robots.txt check |
| `skills/scraping/validators.py` | Pydantic models for Places results and `ProspectCreate` |
| `skills/proposals/service_catalog.py` | `ServiceCatalog`: loads `services_catalog.yaml`, scores services per category, formats them for prompts |
| `skills/proposals/generator.py` | `ProposalGenerator`: Claude calls for the email and WhatsApp versions, template loading, contact/agency placeholder substitution, truncation |
| `skills/proposals/templates/*.md` | Per-category prompt templates (restaurant, retail, clinic, gym, beauty salon, generic) |
| `skills/contact/email_sender.py` | `EmailSender`: SMTP (TLS) or SendGrid, guards, opt-out footer, `contacts` logging |
| `skills/contact/sms_sender.py` | `SmsSender`: Twilio SMS, message shortening, E.164 normalization, guards |
| `skills/contact/social_messenger.py` | `SocialMessenger`: Twilio WhatsApp with guards; Instagram/LinkedIn logged as manual tasks |
| `skills/contact/limits.py` | `sent_today_count()`: per-channel count of today's successful sends from the database |
| `skills/dashboard/app.py` | ORM models, `create_app()`, HTML pages and JSON API, background scraping thread |
| `tools/google_maps_tool.py` | CLI `scrape`: runs the scraper, then optional enrichment |
| `tools/enrichment_tool.py` | CLI `enrich`: enrichment for prospects with a website |
| `tools/contact_finder.py` | CLI `find-emails` (homepage + contact page + 13 common paths) and `fix-whatsapp` (E.164 normalization) |
| `tools/proposal_tool.py` | CLI `generate`: Claude generation for one or many prospects |
| `tools/local_proposal_generator.py` | CLI `generate-local`, `regenerate`, `update-whatsapp`: template-based generation, no API |
| `tools/contact_tool.py` | CLI `send` / `send-batch`, including dry runs |
| `tools/notification_tool.py` | Operator alerts by email/SMS (not called anywhere yet) |

## Data model

All tables live in one SQLite file (`data/prospects.db` by default).

| Table | Key columns | Notes |
|---|---|---|
| `prospects` | `place_id` (unique), name, category, address, phone, website, email, social URLs, whatsapp, rating, review_count, distance_km, editorial_summary, review_snippets (JSON), status | status flow: `nuevo` → `propuesta_generada` → `contactado`; `respondido` / `descartado` are set by hand in the dashboard |
| `proposals` | prospect_id, content (email), content_whatsapp, content_phone, services_selected (JSON), word counts, is_sent | a proposal is sent at most once (`is_sent`) |
| `contacts` | prospect_id, proposal_id, channel, recipient, status, sent_at (UTC), error_message | one row per send attempt; drives the daily limit and statistics |
| `opt_outs` | contact_info (primary key), reason | checked before every send |
| `app_config` | key, value | written by the dashboard's configuration page; not read by the generators |

## Data flow

1. **Scrape.**
   - `scrape` resolves the center and radius from its flags, falling back to `DEFAULT_CENTER_*` and `settings.yaml`.
   - For each category, `GoogleMapsScraper._search_category` requests up to 3 pages. It waits 2.5 s before using a `next_page_token`, and applies the configured delay between calls.
   - Each result goes through Place Details, then `ProspectCreate` validation.
   - `_save_prospects` skips any `place_id` that is already stored.
2. **Enrich.**
   - `DataEnricher.enrich_prospect` checks robots.txt, fetches the homepage and parses it with BeautifulSoup/lxml.
   - If no email is found, it follows the first link that looks like a contact page, after another robots.txt check.
   - `find-emails` then tries fixed paths, checking robots.txt for each URL, with a 30 s hard timeout per prospect.
   - Pages with invalid TLS certificates are skipped.
3. **Select services.**
   - `ServiceCatalog.get_services_for_category` scores each service: 3 points when its `best_for` list contains the category, 1 otherwise.
   - S04 (website) scores 10 when the prospect has no website, and S17 (social media) scores 10 when it has no Instagram or Facebook.
   - Ties break by service ID, so the choice is deterministic.
4. **Generate.** There are two paths:
   - **Claude path** (`ProposalGenerator.generate`):
     - builds a user prompt from the category template, the selected services, the business data, the Google editorial summary and review snippets;
     - calls the Messages API twice (email, then WhatsApp at temperature + 0.1);
     - truncates an email above `max_words + 20` at the last full sentence;
     - fills in `[NOMBRE_AGENCIA]`, `[TELEFONO_AGENCIA]` and the other contact placeholders.
   - **Local path** (`LocalProposalGenerator.generate`):
     - picks copy variant `sum(ord(c) for c in name) % 3`;
     - assembles the email, the WhatsApp message and the phone script from per-category hooks, the differentiator paragraph, service one-liners and CTAs.
5. **Send.** `contact_tool.send_proposal` (CLI) and `_send_proposal_via_channel` (dashboard) pick the sender for the channel. Each sender runs these steps in order:
   1. check the opt-out table;
   2. check the contact window (`contact_window_start`–`contact_window_end`, America/Mexico_City);
   3. check `sent_today_count(channel) < max_contacts_per_day`;
   4. check credentials;
   5. send;
   6. write a `contacts` row and, on success, mark the proposal as sent and the prospect as `contactado`.
6. **Report and export.**
   - `stats` (CLI) and `/api/stats` aggregate the tables.
   - `export` writes a CSV, or writes into an existing Google Sheet through a service account.
   - `/api/export/excel` writes an `.xlsx` under `data/exports/`.

## Dashboard API

| Method | Route | Purpose |
|---|---|---|
| GET | `/` (redirects), `/prospects`, `/prospects/<id>`, `/stats`, `/config`, `/search` | HTML pages |
| GET | `/api/prospects` | paginated, filterable list (category, status, minimum rating, maximum distance, has email, text search) |
| GET / PATCH | `/api/prospects/<id>` | detail with proposals and contacts / update notes, status, email or phone |
| GET | `/api/prospects/categories` | category counts |
| POST | `/api/prospects/<id>/generate-proposal` | Claude proposal for one prospect |
| PUT | `/api/proposals/<id>` | edit proposal text |
| POST | `/api/proposals/<id>/send` | send through a channel |
| POST | `/api/batch/generate`, `/api/batch/send` | batch operations |
| GET | `/api/stats` | aggregate statistics |
| GET | `/api/export/csv`, `/api/export/excel` | exports |
| GET/PUT | `/api/config` | key/value settings shown on the configuration page |
| POST / GET | `/api/search`, `/api/search/status` | start a background scrape / poll its progress |
| POST | `/api/optout` | register an opt-out |

There is no authentication. The server binds to `127.0.0.1` by default (`settings.yaml → dashboard.host`).

## Error handling

- **Google Places:** API errors are logged per category and the search continues with the next one. If Place Details fails, the scraper falls back to the Nearby Search fields.
- **Anthropic:** connection, authentication and rate-limit errors are re-raised as `RuntimeError`, with the original exception chained, and a Spanish message the CLI prints. Batch loops count the error and move on.
- **Senders:** they never raise to the caller. They return `{"success": False, "error": ...}` and log the failed attempt to `contacts`.
- **Configuration:** missing keys fall back to placeholders such as `YOUR_GOOGLE_MAPS_API_KEY` and `[TELEFONO_AGENCIA]`, so the CLI and dashboard start. The external call then fails with the provider's error.

## Extension points

- **New business category:**
  1. add it to `settings.yaml → scraping.categories` (a Google Places type);
  2. map related Google types in `GoogleMapsScraper._classify_category`;
  3. optionally add a template in `skills/proposals/templates/` and map it in `ProposalGenerator._load_template`;
  4. optionally add hooks in `tools/local_proposal_generator.py`.
- **Your own services:** edit `config/services_catalog.yaml` (`id`, `name`, descriptions, `best_for`, `benefit`). The S04/S17 overrides in `ServiceCatalog` refer to those IDs, so keep them or update the overrides.
- **Another channel:**
  1. add a sender in `skills/contact/` that follows the same guard order and writes `contacts` rows with its own `channel` value;
  2. use `sent_today_count(db_session, "<channel>")` for the daily limit;
  3. wire it into `contact_tool.send_proposal`, `_send_proposal_via_channel` and the Click `--channel` choices.
- **Another LLM or model:** change `settings.yaml → proposals.model`, or replace the two `messages.create` calls in `ProposalGenerator`. Prompts are module constants (`SYSTEM_PROMPT`, `WHATSAPP_SYSTEM_PROMPT`).
- **Places API (New):** the only module that talks to Google is `skills/scraping/google_maps.py`. A migration replaces `_search_category` and `_place_to_prospect`, and keeps `ProspectCreate` as the contract with the rest of the system.
