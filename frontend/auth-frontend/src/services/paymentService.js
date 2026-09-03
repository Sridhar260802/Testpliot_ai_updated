// src/services/paymentService.js
//
// Loads Razorpay's Checkout.js and opens the payment modal.
//
// ⚠️ IMPORTANT — TEST-MODE LIMITATION:
// This backend has no order-creation or payment-signature-verification
// endpoint yet. This integration opens Razorpay Checkout directly from
// the browser using only a Key ID, which works for testing the UI/UX
// flow, but it is NOT secure for real payments: anyone could open
// devtools and call onSuccess() manually to fake a successful payment.
//
// Before accepting real money, add to the backend:
//   1. POST /payments/create-order — creates a Razorpay order server-side
//      (needs your Razorpay Key SECRET, never put that in frontend code).
//   2. POST /payments/verify — verifies the payment signature Razorpay
//      sends back, using the Key SECRET, before calling update_user_plan.
// Then swap the "amount"-only checkout below for an order_id-based one.

const RAZORPAY_SCRIPT_SRC = "https://checkout.razorpay.com/v1/checkout.js";
const RAZORPAY_KEY_ID = import.meta.env?.VITE_RAZORPAY_KEY_ID;

let scriptLoadPromise = null;

function loadRazorpayScript() {
  if (scriptLoadPromise) return scriptLoadPromise;

  scriptLoadPromise = new Promise((resolve, reject) => {
    if (window.Razorpay) {
      resolve(window.Razorpay);
      return;
    }
    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve(window.Razorpay);
    script.onerror = () => reject(new Error("Failed to load Razorpay checkout script."));
    document.body.appendChild(script);
  });

  return scriptLoadPromise;
}

/**
 * Opens the Razorpay checkout modal.
 * @param {{ amountInRupees: number, planName: string, userEmail?: string, userName?: string }} params
 * @returns {Promise<{ razorpay_payment_id: string }>}
 */
export async function openRazorpayCheckout({ amountInRupees, planName, userEmail, userName }) {
  if (!RAZORPAY_KEY_ID) {
    throw new Error("Payments are not configured. Set VITE_RAZORPAY_KEY_ID in your .env file.");
  }

  await loadRazorpayScript();

  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay({
      key: RAZORPAY_KEY_ID,
      amount: Math.round(amountInRupees * 100), // paise
      currency: "INR",
      name: "TestPilot",
      description: `${planName} Plan Subscription`,
      prefill: { email: userEmail, name: userName },
      theme: { color: "#0b3327" },
      handler: (response) => resolve(response),
      modal: {
        ondismiss: () => reject(new Error("Payment cancelled.")),
      },
    });

    rzp.on("payment.failed", (response) => {
      reject(new Error(response.error?.description || "Payment failed. Please try again."));
    });

    rzp.open();
  });
}
