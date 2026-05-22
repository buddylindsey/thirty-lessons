from django.test.runner import DiscoverRunner


class AppTestRunner(DiscoverRunner):
    def build_suite(self, test_labels=None, **kwargs):
        return super().build_suite(test_labels or ["courses"], **kwargs)
