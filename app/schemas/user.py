from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.security import MAX_PASSWORD_BYTES


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _check_password_fits_bcrypt(cls, value: str) -> str:
        """Refuse proprement (422) ce qui ferait lever une exception à bcrypt.

        La limite porte sur les **octets** et non les caractères : 36 « é »
        tiennent (72 octets), 37 n'y tiennent plus (74 octets).
        """
        encoded = value.encode("utf-8")
        if len(encoded) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password must not exceed {MAX_PASSWORD_BYTES} bytes when "
                f"encoded in UTF-8 (got {len(encoded)}). Accented characters "
                f"count for 2 bytes each."
            )
        return value


class UserLogin(BaseModel):
    username: str
    password: str
