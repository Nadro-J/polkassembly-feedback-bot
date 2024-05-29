import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GUILD_ID = int(os.getenv('GUILD_ID'))
FORUM_CHANNEL = int(os.getenv('FORUM_CHANNEL'))
SIGNATORY_ROLE = int(os.getenv('SIGNATORY_ROLE'))
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REACTION_THRESHOLD = int(os.getenv('REACTION_THRESHOLD'))
APPROVAL_EMOJI = os.getenv('APPROVAL_EMOJI')
REJECTION_EMOJI = os.getenv('REJECTION_EMOJI')
