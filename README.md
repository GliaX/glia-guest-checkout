# glia-guest-checkout

Guest cart and checkout for **ERPNext v16 + frappe/webshop** — lets anonymous
shoppers add to cart, review totals, enter an email and shipping address, and
pay through the store's existing Stripe gateway. No account required.

Built for [glia.org](https://glia.org) during the Shopify → ERPNext migration.

## Why this exists

ERPNext's webshop has **no guest checkout**. There is no way to add to cart or
load `/cart` without an account:

- `webshop.webshop.shopping_cart.cart.update_cart` / `get_cart_quotation` /
  `place_order` are not `allow_guest`; the storefront JS redirects guests to
  `/login` (`webshop.api.get_guest_redirect_on_action`).
- The upstream issue is still open: [frappe/webshop#122 — Allow Adding Items to
  Cart Without Login](https://github.com/frappe/webshop/issues/122) (also #215).
- The webshop cart is a `Quotation` keyed by `contact_email = frappe.session.user`,
  so it is inherently account-scoped.
- ERPNext's `Payment Request` flow is usable for Shopping Cart orders, but
  `make_payment_request` requires login; a recent upstream fix for portal/guest
  checkout ([frappe/erpnext#52844](https://github.com/frappe/erpnext/issues/52844))
  lands after our pinned build.
- `DigiThinkIT/awesome_cart` adds guest management, but it replaces the whole
  cart and last shipped in 2024; it is not a drop-in for webshop v16.

This app adds guest checkout alongside — not instead of — the normal webshop
cart. Logged-in customers keep the stock webshop flow untouched.

## What it does

- **Guest cart** stored in a custom `Guest Cart` doctype, keyed by an HttpOnly
  `guest_cart_id` cookie. One cart per browser, 30-day cookie.
- Whitelisted guest APIs for add / update / remove / get cart and checkout.
- **Storefront JS** intercepts guest clicks on `.btn-add-to-cart` /
  `.btn-add-to-cart-list`, calls the guest API, updates the header count and
  sends the shopper to `/guest_cart`. Logged-in clicks are untouched.
- **`/guest_cart`** page: items, quantities, removal, subtotal, and a guest
  checkout form (email, name, shipping address, phone). No account prompt.
- **Checkout** creates/finds the Customer and Contact, creates a Shipping
  Address, prices a `Quotation` with the webshop's own price list/tax logic,
  converts it to a submitted **Sales Order**, and creates a submitted
  **Payment Request** through the configured `Payment Gateway Account`.
- Returns the Stripe checkout URL and redirects the guest to it.
- **`/guest_order?token=…`** shows the order summary/status for the guest (token
  is random and stored on the cart).
- Customer matching reuses an existing Contact/Customer by email (including
  `Customer.shopify_email` from the Glia migration) before creating a new one.

## Install

```bash
cd /home/frappe/frappe-bench
bench get-app https://github.com/GliaX/glia-guest-checkout
bench --site your.site install-app glia_guest_checkout
bench --site your.site migrate
```

The app ships:
- `Guest Cart` / `Guest Cart Item` doctypes (System Manager only; the guest API
  writes with `ignore_permissions`),
- `/guest_cart` and `/guest_order` website pages,
- `public/js/guest_checkout.js` and `public/css/guest_checkout.css` loaded on
  every website page through `web_include_js` / `web_include_css`.

Requirements:
- ERPNext 16, `frappe/webshop` (version-16), `frappe/payments`.
- `Webshop Settings.payment_gateway_account` configured (Stripe in Glia's case).
- A valid selling price list / Item Prices for the products being sold.

For a container image, add the app in the ERPNext Dockerfile before `bench build`:

```dockerfile
ARG GUEST_CHECKOUT_REPO=https://github.com/GliaX/glia-guest-checkout
ARG GUEST_CHECKOUT_BRANCH=main
RUN bench get-app "${GUEST_CHECKOUT_REPO}" --branch "${GUEST_CHECKOUT_BRANCH}"
# add "glia_guest_checkout" to the apps.txt + assets symlink loops, then:
RUN bench build
```

## API

All endpoints are POST, `allow_guest=True`, and identify the cart from the
`guest_cart_id` cookie:

| Method | Purpose |
|---|---|
| `glia_guest_checkout.api.get_guest_cart` | items, total, currency, count |
| `glia_guest_checkout.api.add_to_cart(item_code, qty=1)` | add/increment |
| `glia_guest_checkout.api.update_guest_cart(item_code, qty)` | set qty; 0 removes |
| `glia_guest_checkout.api.remove_from_cart(item_code)` | remove |
| `glia_guest_checkout.api.guest_checkout(email, full_name, address_line1, city, country, …)` | create order + payment request, return `payment_url` |

The browser calls these with the guest CSRF token (`frappe.csrf_token`, which is
literally `"None"` for guests) in `X-Frappe-CSRF-Token`.

## Data / flow

```
browser cookie guest_cart_id
        │
        ▼
Guest Cart (Open) ──add/update──► Guest Cart Item (item, qty, rate, amount)
        │
        │ checkout (email, name, address)
        ▼
Customer + Contact + Address
        │
        ▼
Quotation (order_type=Shopping Cart, webshop price list/taxes)
        │  submit
        ▼
Sales Order ──make_payment_request──► Payment Request (Stripe)
        │
        ▼
guest redirected to /stripe_checkout?…
        │
        ▼
Payment Request status updated by the gateway/webhook as usual
Guest Cart status=Converted, order_token stored → /guest_order?token=…
```

Document creation runs internally as Administrator (the shopper is a Guest and
has no permissions on Item/Quotation/Sales Order/Payment Request). All inputs are
validated before that; the guest never receives elevated credentials.

## Limitations / roadmap

- **No rate limiting** on the guest APIs yet. Add `frappe.rate_limiter` or a
  reverse-proxy limit before high-traffic exposure.
- **Tax/shipping** are whatever webshop's `apply_cart_settings` calculates for
  the guest Customer/Address; verify Tax Templates and Shipping Rules in the
  target site.
- **Payment success page** is ERPNext's generic `/payment-success`. A branded
  post-payment redirect / email receipt is a follow-up (the order token page is
  already available).
- **No account creation** on checkout; customers can claim an account later.
- **No recurring donations**; one-time orders only.
- **No guest order lookup by email**; only the random order token.
- Guest cart data is intentionally minimal (email only at checkout).
- The storefront's header cart link is rewritten client-side; if JS is disabled,
  `/cart` still asks guests to log in.
- Tested on ERPNext 16.30 / Frappe 16.29 / webshop 0.0.1.

## License

MIT. See `license.txt`.
