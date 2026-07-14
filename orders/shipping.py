"""Zone-based shipping fees. Must stay in sync with the display table in
orders/templates/orders/checkout.html (shippingZones in the inline script)."""
from decimal import Decimal

_ZONES = {
    'Kaduna': (Decimal('1500.00'), ('Kaduna',)),
    'North': (Decimal('2500.00'), (
        'Kano', 'Zaria', 'Jos', 'Katsina', 'Sokoto', 'Kebbi', 'Zamfara',
        'Bauchi', 'Gombe', 'Yobe', 'Borno', 'Adamawa', 'Taraba', 'Niger',
        'Plateau', 'Nasarawa', 'Kogi', 'Benue', 'Kwara',
    )),
    'West': (Decimal('3500.00'), (
        'Lagos', 'Ibadan', 'Abeokuta', 'Akure', 'Osogbo', 'Ado-Ekiti',
        'Ilorin', 'Oyo', 'Ogun', 'Ondo', 'Osun', 'Ekiti',
    )),
    'East': (Decimal('4000.00'), (
        'Enugu', 'Owerri', 'Onitsha', 'Awka', 'Abakaliki', 'Umuahia',
        'Abia', 'Anambra', 'Ebonyi', 'Imo',
    )),
    'South-South': (Decimal('4500.00'), (
        'Port Harcourt', 'Uyo', 'Calabar', 'Yenagoa', 'Asaba', 'Warri',
        'Benin', 'Akwa Ibom', 'Bayelsa', 'Cross River', 'Delta', 'Edo',
        'Rivers',
    )),
}

STATE_ZONES = {
    state: (zone, fee)
    for zone, (fee, states) in _ZONES.items()
    for state in states
}


def get_shipping_info(state):
    """Return (zone, fee) for a deliverable state, or None if unknown."""
    return STATE_ZONES.get(state)
