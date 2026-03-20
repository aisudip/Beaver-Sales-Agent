# models/access_control.py — Data privacy levels and access control
# Example usage
# from models.access_control import PrivacyLevel, AccessControl
# AccessControl.can_access(PrivacyLevel.AGENT, PrivacyLevel.CUSTOMER)  # True
# AccessControl.can_access(PrivacyLevel.CUSTOMER, PrivacyLevel.AGENT)  # False

# Data privacy levels - define who can access what data
class PrivacyLevel:
    PUBLIC = 'public'        # Anyone can access
    CUSTOMER = 'customer'    # Only customer and admins can access
    AGENT = 'agent'          # Only agents and admins can access
    FINANCIAL = 'financial'  # Only financial dept and admins can access
    ADMIN = 'admin'          # Only admins can access

# Define access control rules based on privacy levels
class AccessControl:
    @staticmethod
    def can_access(requester_level: str, data_level: str) -> bool:
        """Check if the requester has access to the data based on privacy levels."""
        # Admin can access everything
        if requester_level == PrivacyLevel.ADMIN:
            return True

        # Same level access is allowed
        if requester_level == data_level:
            return True

        # Financial can access agent data
        if requester_level == PrivacyLevel.FINANCIAL and data_level == PrivacyLevel.AGENT:
            return True

        # Agent can access customer data
        if requester_level == PrivacyLevel.AGENT and data_level == PrivacyLevel.CUSTOMER:
            return True

        # Anyone can access public data
        if data_level == PrivacyLevel.PUBLIC:
            return True

        # By default, access is denied
        return False
