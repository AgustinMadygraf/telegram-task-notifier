def mask_identifier(value: object, prefix: int = 2, suffix: int = 2) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if len(text) <= prefix + suffix:
        return "*" * len(text)
    return f"{text[:prefix]}***{text[-suffix:]}"


def mask_email(value: str) -> str:
    email = value.strip()
    if "@" not in email:
        return mask_identifier(email, prefix=1, suffix=1)
    local_part, domain = email.split("@", 1)
    return f"{mask_identifier(local_part, prefix=1, suffix=1)}@{domain}"
