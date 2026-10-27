# Browser checks

Use Node.js 20 or newer on a dedicated administrator client with access to both
FUXA instances. Install the locked dependency and its Chromium runtime:

```sh
cd tools/validate/browser
npm ci
npx playwright install --with-deps chromium
cd ../../..
node tools/validate/browser/fuxa.cjs .local/acceptance/fuxa
```

The test visits Dashboard-P1 through P4 on both roles, decodes every displayed image,
rejects common encoding artifacts and browser errors, and saves screenshots
plus a JSON report. External HTTP requests are blocked during rendering. It
does not click switches or write process values. Inspect the screenshots as
well: image loading alone does not establish usable layout.

Screenshots and results remain under ignored `.local/`, outside release source.
