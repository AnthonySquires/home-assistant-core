"""Common Dirigera device helpers."""


def split_name_location(full_name: str) -> tuple[str, str | None]:
    """Split a name into parts to identify a type or location of a sensor."""

    if "[" in full_name and "]" in full_name:
        # Extract the string within square brackets and the rest of the string
        location = full_name[full_name.find("[") + 1 : full_name.find("]")]
        real_name = full_name[full_name.find("]") + 1 :].strip()
        return real_name, location

    # If there are no square brackets, return the original string and an empty string
    return full_name, ""
