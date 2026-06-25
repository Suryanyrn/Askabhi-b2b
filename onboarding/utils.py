import secrets
import string
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger('onboarding')

class OTPManager:
    OTP_EXPIRY_SECONDS = 300  # 5 minutes

    @staticmethod
    def _get_cache_key(email):
        return f"otp_{email}"

    @classmethod
    def generate_otp(cls, email):
        """Generates a secure 6-digit OTP and stores it in cache."""
        # Generate a secure 6-digit number
        otp = ''.join(secrets.choice(string.digits) for i in range(6))
        
        # Store in cache with timeout
        cache_key = cls._get_cache_key(email)
        cache.set(cache_key, otp, timeout=cls.OTP_EXPIRY_SECONDS)
        
        logger.debug(f"Generated new OTP for {email}.,{otp}")
        return otp

    @classmethod
    def verify_otp(cls, email, entered_otp):
        """Verifies the OTP against the cache."""
        cache_key = cls._get_cache_key(email)
        cached_otp = cache.get(cache_key)
        
        if not cached_otp:
            logger.warning(f"OTP verification failed for {email}: OTP expired or not requested.")
            return False, "OTP has expired or was not requested."
            
        if cached_otp == entered_otp:
            # OTP is correct, invalidate it so it can't be used again
            cache.delete(cache_key)
            logger.debug(f"OTP successfully verified and invalidated for {email}.")
            return True, "OTP verified successfully."
            
        logger.warning(f"OTP verification failed for {email}: Invalid OTP entered.")
        return False, "Invalid OTP."
