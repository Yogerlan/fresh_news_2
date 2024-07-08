import logging

from robocorp.tasks import task
from RPA.Robocorp.WorkItems import WorkItems

from collectors import APNewsCollector


@task
def collect_news():
    try:
        wi = WorkItems()
        wi.get_input_work_item()
        search_phrase = wi.get_work_item_variable("search_phrase", "")

        if not search_phrase:
            return

        categories = wi.get_work_item_variable("categories", "")
        months = wi.get_work_item_variable("months", 0)
    except KeyError as ex:
        logging.exception(ex)

        return

    collector = APNewsCollector(
        search_phrase,
        categories,
        months,
        timeout=170
    )
    collector.collect_news()
