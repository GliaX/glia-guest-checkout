(function () {
	window.__guestCheckoutLoaded = true;
	function isGuest() {
		return window.frappe && frappe.session && frappe.session.user === "Guest";
	}

	function csrf() {
		return (window.frappe && frappe.csrf_token) || "None";
	}

	function call(method, args) {
		var body = new URLSearchParams();
		Object.keys(args || {}).forEach(function (key) {
			if (args[key] !== undefined && args[key] !== null) body.append(key, args[key]);
		});
		return fetch("/api/method/" + method, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/x-www-form-urlencoded",
				"X-Frappe-CSRF-Token": csrf()
			},
			body: body.toString()
		}).then(function (response) {
			return response.json().then(function (data) {
				if (data.exc || data._server_messages) {
					var message = "Something went wrong. Please try again.";
					try {
						var messages = JSON.parse(data._server_messages || "[]");
						if (messages.length) message = JSON.parse(messages[0]).message || message;
					} catch (e) { /* keep default */ }
					throw new Error(message);
				}
				return data.message;
			});
		});
	}

	function showToast(message, options) {
		options = options || {};
		var host = document.getElementById("glia-toast-host");
		if (!host) {
			host = document.createElement("div");
			host.id = "glia-toast-host";
			host.setAttribute("role", "status");
			host.setAttribute("aria-live", "polite");
			host.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none";
			document.body.appendChild(host);
		}
		var toast = document.createElement("div");
		toast.className = "glia-toast" + (options.type === "error" ? " glia-toast--error" : "");
		toast.style.cssText = "pointer-events:auto;background:#032e38;color:#fff;padding:12px 18px;border-radius:10px;font:15px/1.4 Ubuntu,Arial,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.22);max-width:min(90vw,420px);display:flex;gap:12px;align-items:center";
		if (options.type === "error") toast.style.background = "#8f2d24";
		var text = document.createElement("span");
		text.textContent = message;
		toast.appendChild(text);
		if (options.href) {
			var link = document.createElement("a");
			link.href = options.href;
			link.textContent = options.linkText || "View cart";
			link.style.cssText = "color:#9ff3ee;font-weight:600;text-decoration:underline;white-space:nowrap";
			toast.appendChild(link);
		}
		host.appendChild(toast);
		setTimeout(function () {
			toast.style.transition = "opacity .3s";
			toast.style.opacity = "0";
			setTimeout(function () { toast.remove(); }, 350);
		}, options.type === "error" ? 6000 : 4000);
		return toast;
	}

	function setCount(count) {
		count = parseInt(count, 10) || 0;
		var badge = document.getElementById("glia-cart-count");
		if (badge) {
			badge.textContent = String(count);
			badge.style.display = count > 0 ? "inline-flex" : "none";
		}
		document.cookie = "cart_count=" + count + ";path=/;SameSite=Lax";
	}

	function money(amount, currency) {
		try {
			return new Intl.NumberFormat("en-CA", { style: "currency", currency: currency || "CAD" }).format(amount);
		} catch (e) {
			return "$" + Number(amount).toFixed(2);
		}
	}

	function escapeHtml(value) {
		return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
			return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
		});
	}

	function rewriteCartLinks() {
		if (!isGuest()) return;
		document.querySelectorAll('a[href="/cart"], a[href^="/cart?"]').forEach(function (a) {
			a.setAttribute("href", "/guest_cart");
		});
	}

	function addToCart(itemCode, qty) {
		return call("glia_guest_checkout.api.add_to_cart", { item_code: itemCode, qty: qty || 1 })
			.then(function (cart) {
				setCount(cart.count);
				var badge = document.querySelector(".cart-count, .badge.cart-count, [data-cart-count]");
				if (badge) badge.textContent = String(cart.count);
				showToast("Added to your cart", { href: "/guest_cart", linkText: "View cart" });
				return cart;
			});
	}

	function bindAddToCart() {
		document.addEventListener("click", function (event) {
			if (!isGuest()) return;
			var button = event.target.closest(".btn-add-to-cart, .btn-add-to-cart-list");
			if (!button) return;
			var itemCode = button.getAttribute("data-item-code");
			if (!itemCode) return;
			event.preventDefault();
			event.stopImmediatePropagation();
			if (button.dataset.guestAdding) return;
			button.dataset.guestAdding = "1";
			button.disabled = true;
			addToCart(itemCode, 1).then(function () {
				button.dataset.guestAdding = "";
				button.disabled = false;
			}).catch(function (error) {
				button.dataset.guestAdding = "";
				button.disabled = false;
				showToast(error.message || "Could not add that item.", { type: "error" });
			});
		}, true);
	}

	function renderCart(cart) {
		var empty = document.getElementById("guest-cart-empty");
		var content = document.getElementById("guest-cart-content");
		var tbody = document.getElementById("guest-cart-items");
		var total = document.getElementById("guest-cart-total");
		if (!empty || !content || !tbody) return;

		if (!cart.items.length) {
			empty.hidden = false;
			content.hidden = true;
			setCount(0);
			return;
		}
		empty.hidden = true;
		content.hidden = false;
		setCount(cart.count);

		tbody.innerHTML = cart.items.map(function (item) {
			var image = item.image
				? '<img src="' + escapeHtml(item.image) + '" alt="">'
				: '<span class="guest-cart-no-image">' + escapeHtml((item.item_name || "")[0] || "") + "</span>";
			return (
				'<tr data-item-code="' + escapeHtml(item.item_code) + '">' +
					'<td class="guest-cart-thumb">' + image + "</td>" +
					'<td><a href="/' + escapeHtml(item.route) + '">' + escapeHtml(item.item_name) + "</a></td>" +
					'<td><input class="guest-qty" type="number" min="0" value="' + escapeHtml(item.qty) + '"></td>' +
					"<td>" + money(item.rate, cart.currency) + "</td>" +
					"<td>" + money(item.amount, cart.currency) + "</td>" +
					'<td><button type="button" class="guest-remove" aria-label="Remove">&times;</button></td>' +
				"</tr>"
			);
		}).join("");

		if (total) total.textContent = money(cart.total, cart.currency);
	}

	function loadCart() {
		call("glia_guest_checkout.api.get_guest_cart", {})
			.then(renderCart)
			.catch(function () { /* leave server-rendered state */ });
	}

	function bindCartPage() {
		var tbody = document.getElementById("guest-cart-items");
		if (!tbody) return;

		tbody.addEventListener("change", function (event) {
			if (!event.target.classList.contains("guest-qty")) return;
			var row = event.target.closest("tr");
			var code = row && row.getAttribute("data-item-code");
			var qty = parseInt(event.target.value, 10) || 0;
			if (!code) return;
			call("glia_guest_checkout.api.update_guest_cart", { item_code: code, qty: qty })
				.then(renderCart)
				.catch(function (error) { showToast(error.message || "Something went wrong.", { type: "error" }); });
		});

		tbody.addEventListener("click", function (event) {
			var remove = event.target.closest(".guest-remove");
			if (!remove) return;
			var row = remove.closest("tr");
			var code = row && row.getAttribute("data-item-code");
			if (!code) return;
			call("glia_guest_checkout.api.remove_from_cart", { item_code: code })
				.then(renderCart)
				.catch(function (error) { showToast(error.message || "Something went wrong.", { type: "error" }); });
		});

		var form = document.getElementById("guest-checkout-form");
		if (form) {
			form.addEventListener("submit", function (event) {
				event.preventDefault();
				var errorBox = document.getElementById("guest-checkout-error");
				var button = form.querySelector("button[type=submit]");
				if (errorBox) { errorBox.hidden = true; errorBox.textContent = ""; }

				var values = {};
				new FormData(form).forEach(function (value, key) { values[key] = value; });
				var country = String(values.country || "Canada").trim().toLowerCase();
				var isCanada = ["canada", "ca", "can"].indexOf(country) !== -1;
				if (isCanada && !String(values.state || "").trim()) {
					if (errorBox) { errorBox.hidden = false; errorBox.textContent = "Please choose your province so we can apply the correct tax."; }
					return;
				}
				if (button) { button.disabled = true; button.textContent = "Redirecting to payment…"; }

				call("glia_guest_checkout.api.guest_checkout", values)
					.then(function (result) {
						window.location.href = result.payment_url;
					})
					.catch(function (error) {
						if (button) { button.disabled = false; button.textContent = "Continue to payment"; }
						if (errorBox) { errorBox.hidden = false; errorBox.textContent = error.message; }
					});
			});
		}

		loadCart();
	}

	function boot() {
		window.__guestCheckoutBoot = (window.__guestCheckoutBoot || 0) + 1;
		if (!isGuest()) return;
		rewriteCartLinks();
		if (!window.__guestCheckoutBound) {
			window.__guestCheckoutBound = true;
			bindAddToCart();
			if (window.location.pathname === "/guest_cart") bindCartPage();
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
	[100, 500, 1500].forEach(function (ms) { setTimeout(boot, ms); });
})();
