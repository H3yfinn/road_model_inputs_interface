# PRC replacement-sales sales shares

`module1_final_value_overrides_05PRC.csv` is a separate, optional final override package for PRC Target sales shares.

The package keeps the existing 9th-edition-derived interface shares in years where the current source has positive sales. It replaces only the zero-sales years with shares calculated from surviving vehicle cohorts and replacement sales, using the PRC survival and vintage profiles from `leap_transport`.

The file is intentionally kept in this subfolder so it can be updated independently of the general per-economy override file. The static-package builder discovers one-level specialist override folders and overlays these projected rows after the ordinary processed-source rows.

Regenerate with:

```text
python back-end/scripts/generate_prc_sales_share_overrides.py
```
