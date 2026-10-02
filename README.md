# Kido Editorial — Odoo 17

Deployment repository containing only the `kido_editorial` addon.
No database, credentials, customer exports, inventory counts or payment keys.

Target: staging container 4502, `kidoessence-pre.binhex.cloud`.
Do not connect this branch to production container 1730.

Install dependencies from the manifest and the addon through the hosting procedure.
The design is disabled on installation. Preview: `/kido-preview` as a website designer.
Map editorial rows to verified real products before activation. Preserve Odoo's native
stock, prices, taxes, delivery and checkout; never restore staging over production.

Before deploying, back up staging and confirm real SMTP/payment providers are disabled.
After installation, validate server logs, QWeb compilation, desktop/mobile rendering,
Website editing, questionnaire, native cart and sandbox checkout.

Addon code: LGPL-3 as declared in `__manifest__.py`. Font licenses are included in
`static/src/fonts`. Brand/product assets retain their respective rights.
