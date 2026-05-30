from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PddStore:
    id: str
    name: str
    database_id: str
    data_source_id: str


PDD_STORES = [
    PddStore(
        id="22",
        name="1店：利德仕官方旗舰店",
        database_id="357dcb3771b34488a3cef83a4cb23ac0",
        data_source_id="0d0674e1-9831-4873-9e7a-de5eda794306",
    ),
    PddStore(
        id="222",
        name="2店：LEEDIS官方旗舰店",
        database_id="2365ddf5ce8c4e3ea0efb59b9d66a2e1",
        data_source_id="029c847c-ab5b-466c-addc-dc00a702a5ae",
    ),
    PddStore(
        id="223",
        name="3店：利德仕旗舰店",
        database_id="22d40ef7b54f48bfbd58486f259bdccf",
        data_source_id="188eb470-bccf-4fe9-950e-0435ca1477bd",
    ),
    PddStore(
        id="224",
        name="4店：珂琪艺官方旗舰店",
        database_id="bc351f09d4d0467295186da18fdce929",
        data_source_id="378f565d-364b-4486-b562-5b4c1bafad77",
    ),
    PddStore(
        id="225",
        name="5店：固家恒五金旗舰店",
        database_id="ac6d5a0f8e1c454d9b52bea258a4e769",
        data_source_id="7662809d-83ec-4b0d-8e3b-20fb243273ef",
    ),
    PddStore(
        id="226",
        name="6店：梵居匠五金旗舰店",
        database_id="6e204dcae17b4ce98a6d05357b997ed2",
        data_source_id="c046b3ee-0a17-4652-a0ff-49be7dd1e3e1",
    ),
    PddStore(
        id="227",
        name="7店：适家旗舰店",
        database_id="0464cb903b9d41c688801196b9ec42ab",
        data_source_id="2bb39a5e-eaa4-4ca4-b42c-afba2b8cde4f",
    ),
]

PDD_STORE_BY_ID = {store.id: store for store in PDD_STORES}


def get_store(store_id: str) -> PddStore:
    try:
        return PDD_STORE_BY_ID[store_id]
    except KeyError as exc:
        valid_ids = ", ".join(PDD_STORE_BY_ID)
        raise ValueError(f"未知店铺 ID：{store_id}，可用值：{valid_ids}") from exc


def get_store_ids(selection: str) -> list[str]:
    if selection == "all":
        return [store.id for store in PDD_STORES]

    store_ids = [item.strip() for item in selection.split(",") if item.strip()]
    for store_id in store_ids:
        get_store(store_id)
    return store_ids
