app_name = "glia_guest_checkout"
app_title = "Glia Guest Checkout"
app_publisher = "Glia"
app_description = "Guest cart and checkout for ERPNext webshop"
app_email = "info@glia.org"
app_license = "mit"

required_apps = ["erpnext", "webshop", "payments"]

# Website assets
web_include_js = ["/assets/glia_guest_checkout/js/guest_checkout.js"]
web_include_css = ["/assets/glia_guest_checkout/css/guest_checkout.css"]

after_install = "glia_guest_checkout.install.after_install"
