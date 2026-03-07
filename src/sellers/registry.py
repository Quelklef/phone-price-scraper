from sellers.amazon import SELLER as AMAZON
from sellers.backmarket import SELLER as BACKMARKET
from sellers.ebay import SELLER as EBAY
from sellers.swappa import SELLER as SWAPPA

SELLERS = (SWAPPA, EBAY, AMAZON, BACKMARKET)
SELLER_BY_KEY = {seller.key: seller for seller in SELLERS}
