from django.core.paginator import Paginator


class PaginatorMixin:
    def my_pagination(self, context, per_page=10):
        paginator = Paginator(context['post_list'], per_page)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        page_obj = paginator.get_page(1)
        context['page_obj'] = page_obj
        return context
