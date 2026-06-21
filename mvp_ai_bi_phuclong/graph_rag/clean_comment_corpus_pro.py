import json
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple
import pandas as pd

# ==========================================
# 1. CẤU HÌNH ĐƯỜNG DẪN & THAM SỐ HỆ THỐNG
# ==========================================
BASE_DIR = Path(__file__).resolve().parents[1]
INPUT = BASE_DIR / "data" / "silver" / "silver_social_comments.csv"

OUT_DIR = BASE_DIR / "graph_rag" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLEAN_OUT = OUT_DIR / "clean_comment_corpus_pro.csv"
REJECT_OUT = OUT_DIR / "rejected_comment_corpus_pro.csv"
REPORT_OUT = OUT_DIR / "clean_comment_corpus_report_pro.md"
STATS_OUT = OUT_DIR / "clean_comment_corpus_stats_pro.json"

MIN_CHAR_LEN = 14
MIN_TOKEN_LEN = 4

# ==========================================
# 2. DANH SÁCH TỪ NHIỄU & TAXONOMY
# ==========================================
PERSON_NAME_NOISE = {
    "nguyen", "nguyễn", "trần", "tran", "lê", "le", "hoàng", "hoang", "phạm", "pham",
    "bảo", "hồng", "ngọc", "thảo", "phương", "linh", "tuấn", "thanh", "huyền",
    "bích", "minh", "vũ", "kiều", "hưng", "thiên", "tiến", "nam", "hữu",
}

GENERIC_NOISE = {
    "tao", "tui", "mình", "bạn", "ơi", "nha", "nhé", "ạ", "ha", "haha",
    "hihi", "hehe", "kkk", "kkkk", "lol", "fl", "ib", "rep", "tag",
    "cái", "này", "kia", "đó", "thấy", "lại", "đâu", "xin", "mới",
}

# Tối ưu hiệu năng: Gộp 2 bộ từ nhiễu thành 1 Set duy nhất để kiểm tra với độ phức tạp O(1)
ALL_NOISE_SET = PERSON_NAME_NOISE.union(GENERIC_NOISE)

BUSINESS_TAXONOMY = {
    "product_taste_quality": [
        "ngon", "dở", "ngọt", "đắng", "nhạt", "đậm", "vị", "trà", "sữa",
        "matcha", "topping", "kem", "đá", "chất lượng", "món", "nước",
        "uống", "trân châu", "hồng trà", "trà sữa", "trà sen", "bánh",
        "sandwich", "ăn sáng", "mật ong", "bưởi",
    ],
    "price_promotion": [
        "giá", "đắt", "rẻ", "voucher", "mã", "giảm", "khuyến mãi", "ưu đãi",
        "sale", "deal", "combo", "freeship", "áp dụng", "mua", "tặng",
        "mã giảm", "giảm giá",
    ],
    "app_payment_order": [
        "app", "thanh toán", "momo", "vnpay", "bank", "online", "đặt hàng",
        "order", "lỗi app", "không thanh toán", "đơn hàng", "mã đơn", "qr",
        "chuyển khoản",
    ],
    "service_store_staff": [
        "nhân viên", "phục vụ", "thái độ", "quầy", "xếp hàng", "chậm",
        "nhanh", "dịch vụ", "order", "tư vấn", "bảo vệ",
    ],
    "delivery_waiting": [
        "giao hàng", "ship", "shipper", "đợi", "chờ", "chờ lâu", "lâu",
        "trễ", "giao", "đơn", "delay", "nhận hàng", "đặt giao",
    ],
    "branch_availability": [
        "chi nhánh", "cửa hàng", "quán", "mở", "đóng", "gần", "xa",
        "địa chỉ", "ở đâu", "hết món", "còn món", "khu vực", "tỉnh",
        "thành phố", "chỗ", "có chỗ",
    ],
    "brand_love_content": [
        "thích", "yêu", "mê", "xinh", "đẹp", "trend", "viral", "clip",
        "video", "content", "hình", "ảnh", "review", "quay", "nhạc",
    ],
}

# ==========================================
# 3. TỐI ƯU HÓA REGEX (PRE-COMPILED REGEX)
# ==========================================
# Gom toàn bộ patterns thành một biểu thức duy nhất để quét chuỗi 1 lần thay vì dùng vòng lặp duyệt từng pattern
SOCIAL_META_PATTERNS = [
    r"\bbình luận\d*\b", r"\blượt chia\b", r"\bchia sẻ\b", r"\bcảm xúc\b",
    r"\blượt thích\b", r"\blượt xem\b", r"\btheo dõi\b"
]
SOCIAL_META_REGEX = re.compile("|".join(SOCIAL_META_PATTERNS), re.IGNORECASE)

NOISE_PATTERNS = [
    r"^\s*@", r"\btag\b", r"\bib\b", r"\brep\b", r"\bpass\b", r"\binbox\b",
    r"^\s*(ha|haha|hihi|hehe|kkk|kaka)+\s*$"
]
NOISE_REGEX = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

# Các mẫu dọn dẹp văn bản cố định
URL_CLEAN_REGEX = re.compile(r"http\S+|www\S+")
MENTION_TAG_REGEX = re.compile(r"@\w+|#\w+")
SPECIAL_CHAR_REGEX = re.compile(r"[^0-9a-zA-ZÀ-ỹ_\s]")
MULTIPLE_SPACES_REGEX = re.compile(r"\s+")
REPEATED_CHARS_REGEX = re.compile(r"([a-zA-ZÀ-ỹ])\1{2,}")


# ==========================================
# 4. CÁC HÀM XỬ LÝ & ĐÁNH GIÁ CHẤT LƯỢNG
# ==========================================
def normalize_text(text: Any) -> str:
    text = str(text).lower()
    text = URL_CLEAN_REGEX.sub(" ", text)
    text = MENTION_TAG_REGEX.sub(" ", text)
    text = SPECIAL_CHAR_REGEX.sub(" ", text)
    return MULTIPLE_SPACES_REGEX.sub(" ", text).strip()


def compact_repeated_chars(text: str) -> str:
    # giảm kiểu "ngonnnnn", "đẹpppp" -> "ngonn", "đẹpp"
    return REPEATED_CHARS_REGEX.sub(r"\1\1", text)


def token_noise_ratio(tokens: List[str]) -> float:
    if not tokens:
        return 1.0
    # Tối ưu: Kiểm tra qua Set tổng với độ phức tạp O(1) cực nhanh
    noise_count = sum(1 for token in tokens if token in ALL_NOISE_SET)
    return noise_count / len(tokens)


def taxonomy_scores(text: str) -> Dict[str, int]:
    scores = {}
    for topic, keywords in BUSINESS_TAXONOMY.items():
        score = 0
        for keyword in keywords:
            if keyword in text:
                score += 2 if " " in keyword else 1
        scores[topic] = score
    return scores


def classify_business_topic(text: str) -> Tuple[str, float, Dict[str, int]]:
    scores = taxonomy_scores(text)
    best_topic = max(scores, key=scores.get)
    best_score = scores[best_topic]
    total_score = sum(scores.values())

    if best_score <= 0:
        return "general_social_or_noise", 0.0, scores

    confidence = best_score / max(1, total_score)
    return best_topic, confidence, scores


def compute_comment_quality(text: str, brand: str, sentiment_label: str, risk_group: str) -> Dict[str, Any]:
    clean = compact_repeated_chars(normalize_text(text))
    tokens = clean.split()

    reject_reasons = []

    # Kiểm tra điều kiện độ dài
    if len(clean) < MIN_CHAR_LEN:
        reject_reasons.append("too_short_char")
    if len(tokens) < MIN_TOKEN_LEN:
        reject_reasons.append("too_short_token")

    # Tối ưu: Quét mạng xã hội & mẫu từ nhiễu bằng regex đã gộp (Chạy 1 lần thay vì lặp qua từng pattern)
    if SOCIAL_META_REGEX.search(clean):
        reject_reasons.append("social_meta_noise")
    if NOISE_REGEX.search(clean):
        reject_reasons.append("noise_pattern")

    noise_ratio = token_noise_ratio(tokens)
    if noise_ratio >= 0.60:
        reject_reasons.append("high_token_noise_ratio")

    business_topic, business_match_confidence, score_map = classify_business_topic(clean)

    has_business_signal = business_topic != "general_social_or_noise"
    has_sentiment = str(sentiment_label).lower() in {"positive", "neutral", "negative"}
    has_risk = str(risk_group).lower() not in {"none", "nan", "unknown", ""}

    length_score = min(1.0, len(tokens) / 18)
    business_score = business_match_confidence if has_business_signal else 0.0
    noise_score = 1.0 - noise_ratio
    sentiment_score = 1.0 if has_sentiment else 0.5
    risk_score = 1.0 if has_risk else 0.3

    comment_quality_score = (
        0.40 * business_score
        + 0.25 * length_score
        + 0.20 * noise_score
        + 0.10 * sentiment_score
        + 0.05 * risk_score
    )

    if business_topic == "brand_love_content" and len(tokens) >= 5 and noise_ratio < 0.55:
        comment_quality_score += 0.10

    comment_quality_score = max(0.0, min(1.0, comment_quality_score))

    if comment_quality_score < 0.35:
        reject_reasons.append("low_comment_quality_score")

    accept = len(reject_reasons) == 0

    return {
        "text_clean": clean,
        "text_for_model": clean,
        "token_count": len(tokens),
        "noise_token_ratio": round(noise_ratio, 4),
        "business_topic_rule": business_topic,
        "business_match_confidence": round(business_match_confidence, 4),
        "comment_quality_score": round(comment_quality_score, 4),
        "reject_reason": "|".join(reject_reasons),
        "is_accepted": bool(accept),
        "taxonomy_score_map": score_map,
    }


# ==========================================
# 5. TIẾN TRÌNH CHẠY CHÍNH (MAIN PROCESS)
# ==========================================
def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT}")

    df = pd.read_csv(INPUT, encoding="utf-8-sig", low_memory=False)

    required = ["brand", "platform", "text", "sentiment_label", "risk_group"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    # Lọc thương hiệu mục tiêu
    df = df[df["brand"].isin(["phuc_long", "highlands", "katinat"])].copy()

    # Tối ưu vòng lặp: Sử dụng list comprehension kết hợp zip() chạy nhanh hơn đáng kể so với .iterrows() truyền thống
    quality_rows = [
        compute_comment_quality(text, brand, sentiment, risk)
        for text, brand, sentiment, risk in zip(
            df["text"].fillna(""),
            df["brand"].fillna("unknown"),
            df["sentiment_label"].fillna("unknown"),
            df["risk_group"].fillna("none")
        )
    ]

    quality_df = pd.DataFrame(quality_rows)
    out = pd.concat([df.reset_index(drop=True), quality_df], axis=1)

    # Đánh dấu dữ liệu trùng lặp sau khi chuẩn hóa văn bản
    out["duplicate_key"] = (
        out["brand"].astype(str) + "|" +
        out["platform"].astype(str) + "|" +
        out["text_clean"].astype(str)
    )
    out["is_duplicate_clean_text"] = out.duplicated("duplicate_key", keep="first")

    # Phân loại Accepted và Rejected
    accepted = out[out["is_accepted"] & ~out["is_duplicate_clean_text"]].copy()
    rejected = out[(~out["is_accepted"]) | out["is_duplicate_clean_text"]].copy()

    # Sắp xếp danh sách chấp nhận theo độ chất lượng giảm dần
    accepted = accepted.sort_values(
        ["comment_quality_score", "business_match_confidence"],
        ascending=False,
    )

    # Xuất các file kết quả dữ liệu sạch
    accepted.to_csv(CLEAN_OUT, index=False, encoding="utf-8-sig")
    rejected.to_csv(REJECT_OUT, index=False, encoding="utf-8-sig")

    # Thống kê tổng hợp dữ liệu
    stats = {
        "status": "PASS",
        "raw_comments": int(len(df)),
        "accepted_comments": int(len(accepted)),
        "rejected_comments": int(len(rejected)),
        "accepted_ratio": round(len(accepted) / max(1, len(df)), 4),
        "duplicate_rejected": int(out["is_duplicate_clean_text"].sum()),
        "business_topic_distribution": accepted["business_topic_rule"].value_counts().to_dict(),
        "reject_reason_distribution": rejected["reject_reason"].value_counts().head(30).to_dict(),
    }

    STATS_OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    # Xây dựng báo cáo Markdown
    report = [
        "# Clean Comment Corpus Pro Report",
        "",
        f"- Raw comments: {stats['raw_comments']:,}",
        f"- Accepted comments: {stats['accepted_comments']:,}",
        f"- Rejected comments: {stats['rejected_comments']:,}",
        f"- Accepted ratio: {stats['accepted_ratio']:.2%}",
        f"- Duplicate rejected: {stats['duplicate_rejected']:,}",
        "",
        "## Business topic distribution",
        accepted["business_topic_rule"].value_counts().to_markdown(),
        "",
        "## Reject reason distribution",
        rejected["reject_reason"].value_counts().head(30).to_markdown(),
        "",
        "## Academic note",
        (
            "Bước này làm sạch comment trước khi đưa vào topic model. "
            "Các comment quá ngắn, comment metadata mạng xã hội, comment chứa tỷ lệ từ nhiễu cao, "
            "comment trùng lặp sau chuẩn hóa và comment không đạt comment_quality_score tối thiểu "
            "được loại khỏi corpus modeling. Cách này giúp giảm nguy cơ mô hình học topic từ tên người, "
            "từ lóng hoặc tín hiệu tương tác không có ý nghĩa quản trị."
        ),
    ]

    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()