import random
import string

def generate_id(prefix):
    chars = string.ascii_lowercase + string.digits
    return prefix + "_" + "".join(random.choice(chars) for _ in range(8))