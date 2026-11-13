from app.core.config import Settings


def test_neon_style_url_is_converted_for_asyncpg() -> None:
    url = "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require&channel_binding=require"
    assert Settings(database_url=url).database_url == (
        "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb?ssl=require"
    )


def test_asyncpg_url_is_left_alone() -> None:
    url = "postgresql+asyncpg://screeniq:screeniq@localhost:5432/screeniq"
    assert Settings(database_url=url).database_url == url
