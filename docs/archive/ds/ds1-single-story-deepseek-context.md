# DS1 — Single Story DeepSeek Context

DS1 is an isolated vertical slice for `27-jiajue-008`:

```text
reviewed repository evidence
    ↓
data/generated/ds1/27-jiajue-008-context.json
    ↓
DeepSeek candidate
    ↓
data/annotation/ds1-review.json
    ↓ accepted / edited only
site/public/generated/ds1/27-jiajue-008.json
```

The context bundle is built from the existing SC1 Story text and annotation
evidence, HR0/HR0.1 reviewed situation records, reviewed H0C fact rows, and
the already extracted Story-local S1 Jianshu assertions. The API prompt sends
only that bundle and requires evidence references for substantive claims.

Run the real call with:

```bash
export DEEPSEEK_API_KEY="..."
python3 scripts/run_ds1.py --story 27-jiajue-008
```

Inspect the candidate at:

```text
data/generated/ds1/27-jiajue-008.json
```

Edit the human decision here:

```text
data/annotation/ds1-review.json
```

Set `decision` to `accepted` to publish the candidate, or to `edited` and put
the reviewed DS1 five-field object in `edited_value`. Use `rejected` or
`pending` to keep it out of the site. Then run `npm run build:site` to update
the optional static preview. The preview is fetched only inside the existing
NL0 Story/Sketch view and is not part of `sc1-site.json` or canonical history.

Validate the isolated boundary with:

```bash
python3 scripts/validate_ds1.py
```

DS1 output is experimental, non-canonical, and never writes back to Gold,
historical facts, Persons, Relations, or production Story scope.
