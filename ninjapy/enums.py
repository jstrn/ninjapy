from enum import Enum

class NodeApprovalMode(str, Enum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    REJECT = "REJECT"

class Severity(str, Enum):
    NONE = "NONE"
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"

class Priority(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class InstallerType(str, Enum):
    WINDOWS_MSI = "WINDOWS_MSI"
    MAC_DMG = "MAC_DMG"
    MAC_PKG = "MAC_PKG"
    LINUX_DEB = "LINUX_DEB"
    LINUX_RPM = "LINUX_RPM" 