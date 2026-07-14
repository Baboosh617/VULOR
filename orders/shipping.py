"""Zone-based shipping fees — the single source of truth.

The checkout page's JS reads this table via a json_script block rendered by
the checkout view, so fees and delivery estimates can only be edited here.
"""
from decimal import Decimal

_ZONES = {
    'Kaduna': (Decimal('1500.00'), '2-3', ('Kaduna',)),
    'North': (Decimal('2500.00'), '3-4', (
        'Kano', 'Zaria', 'Jos', 'Katsina', 'Sokoto', 'Kebbi', 'Zamfara',
        'Bauchi', 'Gombe', 'Yobe', 'Borno', 'Adamawa', 'Taraba', 'Niger',
        'Plateau', 'Nasarawa', 'Kogi', 'Benue', 'Kwara',
    )),
    'West': (Decimal('3500.00'), '3-5', (
        'Lagos', 'Ibadan', 'Abeokuta', 'Akure', 'Osogbo', 'Ado-Ekiti',
        'Ilorin', 'Oyo', 'Ogun', 'Ondo', 'Osun', 'Ekiti',
    )),
    'East': (Decimal('4000.00'), '4-6', (
        'Enugu', 'Owerri', 'Onitsha', 'Awka', 'Abakaliki', 'Umuahia',
        'Abia', 'Anambra', 'Ebonyi', 'Imo',
    )),
    'South-South': (Decimal('4500.00'), '4-7', (
        'Port Harcourt', 'Uyo', 'Calabar', 'Yenagoa', 'Asaba', 'Warri',
        'Benin', 'Akwa Ibom', 'Bayelsa', 'Cross River', 'Delta', 'Edo',
        'Rivers',
    )),
}

STATE_ZONES = {
    state: (zone, fee)
    for zone, (fee, _days, states) in _ZONES.items()
    for state in states
}


def get_shipping_info(state):
    """Return (zone, fee) for a deliverable state, or None if unknown."""
    return STATE_ZONES.get(state)


def client_table():
    """JSON-safe {state: {price, days, zone}} for the checkout page script."""
    return {
        state: {'price': float(fee), 'days': days, 'zone': zone}
        for zone, (fee, days, states) in _ZONES.items()
        for state in states
    }
