# Source governance and licence ledger

Checked 2026-10-28 against the linked primary pages. This is recorded terms-page evidence and a conservative engineering policy, **not legal clearance**. `config/sources.yaml` is the machine-readable candidate inventory. Every source is disabled; this wave retrieved pages for review, not datasets or model weights. Empty `retrieved_at` and `sha256`, and `last_outcome: not_attempted`, refer to dataset/model retrieval, not the web review. No real data is bundled.

`verified` means a relevant explicit use grant was found, subject to its stated conditions; it does not prove coverage, accuracy or working ingestion. `restricted` means relevant limitations were found. `unverified` means no adequate permission was established. Source confidence describes official versus unofficial provenance, not statistical quality. Unknown permission is never permission to redistribute.

## Candidate evidence

| Candidate | Status | Inspected evidence and implications |
|---|---|---|
| AMFI monthly flows and NAV | restricted | [AMFI terms](https://www.amfiindia.com/terms-of-use) limit site use to personal/non-commercial purposes and prohibit publication, derivatives and significant electronic storage. The site grants no general dataset redistribution permission. Obtain applicable written permission/clearer dataset-specific terms before bulk retrieval, processing for a public product, or committing snapshots. [AMFI landing page](https://www.amfiindia.com/) was inspected; no report endpoint is approved here. |
| mfapi.in NAV wrapper | unverified | [Provider page](https://www.mfapi.in/) describes free access but its terms/privacy footer points back to that page. No substantive data licence was found. It is an unofficial wrapper, not AMFI permission. Cross-check source provenance and never use it to bypass upstream restrictions. |
| NSE / India VIX | restricted | [NSE data usage policy](https://www.nseindia.com/static/market-data/nse-data-policy) makes use/sharing/distribution subject to identified terms. No applicable dataset entitlement was verified. General terms URL fetch failed in the review tool. No VIX download endpoint or availability is asserted. |
| NSE Indices / Nifty | restricted | [NSE Indices terms](https://www.niftyindices.com/terms-of-use), sections 7, 12 and 20, restrict copying/distribution, automated collection without written consent, and non-personal use. Public availability does not authorize automated collection or repository snapshots. |
| yfinance / Yahoo | restricted | [Maintainer README](https://github.com/ranaroussi/yfinance) distinguishes the Apache-2.0 wrapper from upstream data rights, describes it as unaffiliated with Yahoo, and states personal-use intent. Actual Yahoo terms must be checked for an intended use. Neither ^NSEI nor ^INDIAVIX was queried. |
| RBI DBIE | unverified | [Official DBIE portal](https://data.rbi.org.in/DBIE/) resolves but exposed no text in the review tool. The [RBI DBIE brochure](https://dbieold.rbi.org.in/DBIE/doc/Brochure%20on%20DBIE%20-2022%20English.pdf) describes downloads and research/analysis; that is not treated as a blanket redistribution licence. Exact series rights, revisions and publication times remain to inspect. |
| RBI RSS | unverified | [Official RSS directory](https://www.rbi.org.in/Scripts/rss.aspx) describes subscription. No adequate storage/republication grant was established. Disabled until feed-specific terms are resolved. |
| Federal Reserve Board RSS | verified, conditional | [Official feed directory](https://www.federalreserve.gov/feeds/feeds.htm) links the [press-release feed](https://www.federalreserve.gov/feeds/press_all.xml). [Board disclaimer](https://www.federalreserve.gov/disclaimer.htm) permits copying/distribution of Board information unless otherwise indicated, requests citation, and excludes third-party material and protected insignia. This is an optional global-rates context candidate, not an India-news replacement. The tool could not parse the XML content type; operational parsing is untested. |
| GDELT | verified, conditional | [Official terms](https://gdeltproject.org/about.html) expressly permit use and redistribution of GDELT-released datasets with citation and link. [Data directory](https://gdeltproject.org/data.html) documents access modes. This does not grant publisher article rights. DOC versus GKG historical coverage, query behavior and rate limits remain unverified; do not promise a history length. |
| ProsusAI/finbert | restricted | The [current model card](https://huggingface.co/ProsusAI/finbert) explicitly gives weights CC-BY-NC-SA-4.0 terms and identifies separate training-data restrictions. Do not substitute the training-code licence for weights rights. No weights downloaded. |
| yiyanghkust/finbert-tone | unverified | The [model card](https://huggingface.co/yiyanghkust/finbert-tone) supplies usage/citation guidance but no explicit weights licence was found in the inspected card. Linked code rights do not establish checkpoint rights. Disabled. |
| VADER offline fallback | verified, conditional | The [maintainer repository](https://github.com/cjhutto/vaderSentiment) describes the tool/lexicon under MIT and requests research citation. Retain licence/copyright notices; pin and hash the exact package/lexicon before use. Input-headline permissions remain independent. No model/package installed by this task. |

These findings create a real dependency: **AMFI and Nifty public snapshot commitments in the architecture cannot be presumed achievable under the reviewed terms.** Source inspection must establish a permissible route or the integrator must approve a revised data/demo plan. Synthetic fixtures remain useful for interfaces but cannot satisfy real-data gates.

## Retrieval and fallback policy

1. Keep retrieval separate from app rendering. Config is a review inventory, not an executable downloader; `enabled: false` on every entry. Terms must be rechecked when enabling a source or changing intended use.
2. Before acquisition record source/terms URL, checked date, scope of permission and attribution. Unknown/restricted entries require an applicable permission decision; a successful HTTP response is not such a decision. Record a policy-blocked attempt without a file hash when appropriate.
3. Configured limits are local proposed defaults, not provider-published quotas: timeout 30 seconds, at most 3 attempts, at least 2 seconds between requests, maximum response 10 MB. Honor Retry-After; stop on access denial and schema/format breaks. Do not bypass access controls or retry permission failures. Provider-specific stricter rules win. No retriever is implemented in this wave.
4. Keep authorized raw bytes immutable under `data/raw/<source>/<retrieval timestamp>/`; calculate SHA-256 over original bytes before parsing. Preserve prior vintages, report period, release evidence and retrieval time separately. Never equate retrieval timestamp with `available_from` without publication evidence.
5. NAV fallback order: permission-cleared AMFI data, then a previously validated and permission-cleared local snapshot. An unofficial wrapper may be used only after both wrapper and underlying rights are settled and provenance is labelled. Market fallback similarly requires permission-cleared official files or a licensed snapshot. Do not silently mix vintages/providers. Missing data yields a visible unavailable state.
6. Commit only files with documented redistribution permission, attribution and checked terms. Raw third-party material remains excluded by `.gitignore`; that exclusion alone does not grant permission to download it. Derived outputs also need scope review. GDELT metadata permission does not extend to full news articles. Store only authorized headline, URL and publication time; no body scraping or personal contact fields.
7. Pin sentiment model/lexicon revision and licence before offline caching. Use an approved fallback rather than downloading weights during app startup. No classifier is installed or measured here; sentiment is display context, never a predictive feature by default.

## Registry interface

`src/fundflow/registry.py` is standard-library only and does no network I/O. Exact CSV order:

```text
source_name,url,data_type,frequency,retrieved_at,terms_url,permitted_use,attribution,redistribution_status,source_confidence,sha256,last_outcome,status,checked_on
```

- `file_sha256(path)` streams bytes; stable across filenames/timestamps.
- `validate_record(record)` requires exact fields, ISO UTC retrieval timestamps when present, ISO checked date, enum statuses and a lowercase 64-character hash for success.
- `read_registry(path)` returns validated dictionaries; a missing ledger returns an empty list, malformed existing CSV fails.
- `write_registry(path, records)` validates all records first, writes/fsyncs a sibling temporary file, then atomically replaces the destination. Failed validation or replacement preserves the previous ledger. Symlink destinations are rejected.
- `append_record(path, record)` preserves prior attempts. **Single writer only**: the integrator serializes calls; concurrent writer locking is not implemented. Readers see complete versions.

Outcomes: `success`, `failed`, `blocked`, `not_attempted`. Only success carries a hash; a successful retrieval requires a timestamp. Failure records carry categorical outcomes, never raw exception bodies. Status and outcome are independent: an authorized retrieval can fail technically. Repeating a retrieval appends a new attempt; consumers choose the last matching row when they need latest outcome.

URLs must be HTTP(S), credential-free and contain no query/fragment. Store the canonical public resource path here; a future retriever requiring nonsecret query parameters must have a separately reviewed parameter manifest rather than silently lose reproducibility. This ledger intentionally rejects all query strings until such a contract exists. Free text rejects control characters, spreadsheet formula prefixes, common credential markers and email addresses. These checks are defense in depth, **not a general PII or secret detector**: callers must only supply public provenance and never request bodies, user records, credentials, raw error traces or local personal paths.

## Executed verification

`.venv/bin/python -m pytest -q tests/test_registry.py tests/test_contracts.py` passed: **48 tests** on 2026-10-28. Tests use synthetic records and prove byte-stable hashing, changed-byte detection, read/write/append, malformed-header rejection, prior-file preservation on invalid input and replacement failure, temporary-file cleanup, credential-bearing URL rejection, status/hash/timestamp checks, and candidate inventory completeness. This result does not establish live download availability or legal permission beyond the recorded terms evidence.
