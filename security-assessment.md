# Security Assessment — SecureHelpDesk

## Overview
A header-based security assessment was performed against the live deployed
frontend using the [Mozilla HTTP Observatory](https://observatory.mozilla.org),
an open-source scanner that evaluates a site's HTTP response headers against
current web security best practices (CSP, HSTS, clickjacking protection,
MIME-sniffing protection, and related browser security controls).

**Target:** `https://securehelpdesk-omega.vercel.app`
**Tool:** Mozilla HTTP Observatory
**Date:** October 2026

## Initial Scan Results

| Metric | Result |
|---|---|
| Grade | **C** |
| Score | 50 / 100 |
| Tests passed | 9 / 12 |

### Findings

| Header | Status | Risk |
|---|---|---|
| Content-Security-Policy | ❌ Missing (−25) | No restriction on which scripts/styles/resources the page may load — the primary browser-level defense against Cross-Site Scripting (XSS). |
| X-Frame-Options | ❌ Missing (−20) | Page could be embedded in a hidden `<iframe>` on a malicious site and used for clickjacking attacks. |
| X-Content-Type-Options | ❌ Missing (−5) | Browser could MIME-sniff a response into executing as an unintended content type. |

## Remediation

Vercel's `headers` configuration was used to apply the missing security
headers at the CDN/edge level (`frontend/vercel.json`):

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' https://securehelpdesk.onrender.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "geolocation=(), microphone=(), camera=()" }
      ]
    }
  ]
}
```

## Post-Fix Scan Results

| Metric | Result |
|---|---|
| Grade | **A+** |
| Score | 115 / 100 |
| Tests passed | 12 / 12 |

All three failed checks now pass. The deployment also picked up a bonus
point for Subresource Integrity being satisfied implicitly (all scripts are
loaded from the same origin).

## Known Follow-Up

The current Content-Security-Policy still allows `'unsafe-inline'` in
`style-src`, which the scanner flags as a minor hardening opportunity. This
was a deliberate tradeoff to avoid breaking existing component styling
without first auditing every inline style in the React app. A future
improvement would be to move all inline styles into CSS classes and tighten
`style-src` to `'self'` only, removing `'unsafe-inline'` entirely.

## Summary

| | Before | After |
|---|---|---|
| Grade | C | **A+** |
| Score | 50/100 | **115/100** |
| Tests passed | 9/12 | **12/12** |
