# Replacement-sales sales shares

This folder contains separate, optional final override packages for Target and Reference sales shares, one file per economy.

Each package keeps the existing 9th-edition-derived interface shares in years where the current source has positive sales. It replaces only zero-sales parent/year combinations with shares calculated from surviving vehicle cohorts and replacement sales, using the corresponding survival and vintage profiles from `leap_transport`. Empty files are retained for economies where no replacement rows are needed.

The files are intentionally kept in this subfolder so they can be updated independently of the ordinary processed-source files. The static-package builder discovers this specialist folder and overlays these projected rows after the ordinary workbook/source rows. The static bundle is the browser/model hand-off, and the generated static files have been updated for all non-empty packages.

Regenerate with:

```text
python back-end/scripts/generate_prc_sales_share_overrides.py
```
