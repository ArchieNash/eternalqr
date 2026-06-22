import os
import stripe
from flask import Blueprint, render_template, redirect, request, flash, url_for, current_app

support_bp = Blueprint('support', __name__)

PRESET_AMOUNTS = [3, 7, 15]
MIN_AMOUNT = 1
MAX_AMOUNT = 500


@support_bp.route('/support')
def index():
    return render_template('support/index.html', presets=PRESET_AMOUNTS)


@support_bp.route('/support/checkout', methods=['POST'])
def checkout():
    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        flash('Payments are not configured yet. Please try again later.', 'error')
        return redirect(url_for('support.index'))

    try:
        raw = request.form.get('amount', '').strip().replace('$', '')
        amount = float(raw)
        if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
            raise ValueError
        amount_cents = int(round(amount * 100))
    except (ValueError, TypeError):
        flash(f'Please enter an amount between ${MIN_AMOUNT} and ${MAX_AMOUNT}.', 'error')
        return redirect(url_for('support.index'))

    base_url = current_app.config.get('APP_BASE_URL', request.host_url.rstrip('/'))

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Support ArchiveHumanity',
                        'description': 'Helping keep memories alive, forever.',
                    },
                    'unit_amount': amount_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{base_url}{url_for('support.success')}",
            cancel_url=f"{base_url}{url_for('support.index')}",
        )
        return redirect(session.url)
    except stripe.error.StripeError as e:
        flash('Something went wrong with the payment. Please try again.', 'error')
        return redirect(url_for('support.index'))


@support_bp.route('/support/thank-you')
def success():
    return render_template('support/success.html')
