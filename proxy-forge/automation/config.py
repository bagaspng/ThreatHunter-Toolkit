from dataclasses import dataclass, field

@dataclass
class TargetConfig:
    url: str
    form_selectors: dict
    robot_checkbox_selector: str
    captcha_input_selector: str
    submit_selector: str
    # Extended fields per specification
    TARGET_URL: str = ""
    FORM_DATA: dict[str, str] = field(default_factory=dict)
    RESOURCE_BLOCK_PATTERNS: list[str] = field(default_factory=lambda: [
        "png", "jpg", "jpeg", "gif", "svg", "css", "woff", "woff2", "mp4", "mp3"
    ])
    TRACKER_DOMAINS: list[str] = field(default_factory=lambda: [
        "google-analytics.com",
        "googletagmanager.com",
        "facebook.net",
        "connect.facebook.net",
        "static.hotjar.com",
        "clarity.ms"
    ])
    TIMEOUT: int = 10
    MAX_RETRIES: int = 3
    RANDOM_DELAY_MIN: float = 0.5
    RANDOM_DELAY_MAX: float = 2.0

QNN_CONFIG = TargetConfig(
    url="https://qnn.net.id/kontak-kami",
    TARGET_URL="https://qnn.net.id/kontak-kami",
    form_selectors={
        "nama": "input[name='nama']",
        "judul": "input[name='judul']",
        "email": "input[name='email']",
        "pesan": "textarea[name='isipesan']"
    },
    FORM_DATA={
        "nama": "Vora Arsitek",
        "judul": "Pengujian Sistem Automasi",
        "email": "vora.xos@test-domain.io",
        "pesan": "Automasi arsitektur sistem tingkat lanjut."
    },
    # Menargetkan label seringkali lebih stabil untuk checkbox bergaya Tailwind/CSS custom
    robot_checkbox_selector="label[for='robotCheck'], input#robotCheck",
    # Fallback: mencari input text yang bukan honeypot atau field form utama
    captcha_input_selector="input[name='captcha_answer'], input[type='text']:not([name='honeypot']):not([name='nama']):not([name='email']):not([name='judul'])",
    submit_selector="button[type='submit']"
)

# Module-level defaults for direct import
TARGET_URL: str = QNN_CONFIG.TARGET_URL or QNN_CONFIG.url
FORM_DATA: dict[str, str] = QNN_CONFIG.FORM_DATA
RESOURCE_BLOCK_PATTERNS: list[str] = QNN_CONFIG.RESOURCE_BLOCK_PATTERNS
TRACKER_DOMAINS: list[str] = QNN_CONFIG.TRACKER_DOMAINS
TIMEOUT: int = QNN_CONFIG.TIMEOUT
MAX_RETRIES: int = QNN_CONFIG.MAX_RETRIES
RANDOM_DELAY_MIN: float = QNN_CONFIG.RANDOM_DELAY_MIN
RANDOM_DELAY_MAX: float = QNN_CONFIG.RANDOM_DELAY_MAX