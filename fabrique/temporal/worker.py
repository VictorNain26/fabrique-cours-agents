"""Worker Temporal de la fabrique. Lancement : `python -m fabrique.temporal.worker`."""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from fabrique.config import reglages
from fabrique.temporal.activites import controler_page, generer_page, publier_page
from fabrique.temporal.workflows import GenerationPage


async def main() -> None:
    parametres = reglages()
    client = await Client.connect(parametres.temporal_host, namespace=parametres.temporal_namespace)

    worker = Worker(
        client,
        task_queue=parametres.temporal_task_queue,
        workflows=[GenerationPage],
        activities=[generer_page, controler_page, publier_page],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
