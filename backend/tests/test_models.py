from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Asset, AssetStatus, Template


def test_asset_and_template_models_persist() -> None:
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as session:
        asset = Asset(
            original_filename="source.mp4",
            stored_filename="asset-1.mp4",
            file_path="storage/uploads/asset-1.mp4",
            status=AssetStatus.UPLOADED.value,
        )
        template = Template(
            name="simple",
            version=1,
            json_spec={"output": {"width": 1080, "height": 1920}},
            is_builtin=True,
        )
        session.add_all([asset, template])
        session.commit()

        stored_asset = session.scalar(select(Asset).where(Asset.id == asset.id))
        stored_template = session.scalar(select(Template).where(Template.id == template.id))

    assert stored_asset is not None
    assert stored_asset.status == AssetStatus.UPLOADED.value
    assert stored_template is not None
    assert stored_template.json_spec["output"]["height"] == 1920
