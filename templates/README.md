# Trial Production Template Library v2

The active built-in template library lives in:

```text
backend/app/template_library.py
```

Built-in templates are now recommended `variant_recipe` records, not complete
one-off render templates. The v2 design is documented in:

```text
docs/ad_variant_template_v2.md
```

Each recipe must include:

- `schema_version: 2`
- `type: variant_recipe`
- `blueprint`
- `render_preset`
- `style_pack`
- `review_notes`

Source authorization is a pre-upload operating requirement for trial partners,
not an in-app template switch or automated validation result.

Slots are part of the recipe contract. Current rendering still compiles to the
FFmpeg source-segment path; AI asset slot binding is the next integration point.
