
# =================================PAGINATION=================================
from rest_framework import pagination
from rest_framework.exceptions import NotFound

class CustomPagination(pagination.PageNumberPagination):
    page_size = 20  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 1000  # Maximum page size allowed
    page_query_param = 'page'

    def paginate_queryset(self, queryset, request, view=None):
        page_number = request.query_params.get(self.page_query_param)
        
        # Store request for use in get_paginated_response
        self.request = request

        try:
            page = super().paginate_queryset(queryset, request, view)
        except NotFound as e:
            raise NotFound(detail=f"Invalid page number: {page_number}")
        
        # If page_size is not provided, use default (20)
        # Don't override to max_page_size as that would return too many records

        return page

    def get_paginated_response(self, data):
        next_page_number = self.page.next_page_number() if self.page.has_next() else None
        previous_page_number = self.page.previous_page_number() if self.page.has_previous() else None
        
        # Build next and previous URLs
        request = getattr(self, 'request', None)
        next_url = None
        previous_url = None
        
        if request:
            base_url = request.build_absolute_uri(request.path)
            # Remove existing query params
            if '?' in base_url:
                base_url = base_url.split('?')[0]
            
            # Get all query params except page
            query_params = request.query_params.copy()
            if 'page' in query_params:
                del query_params['page']
            
            # Build query string
            query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])
            
            if next_page_number:
                next_url = f"{base_url}?page={next_page_number}"
                if query_string:
                    next_url += f"&{query_string}"
            
            if previous_page_number:
                previous_url = f"{base_url}?page={previous_page_number}"
                if query_string:
                    previous_url += f"&{query_string}"
        
        return {
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page_number': self.page.number,
            'page_size': self.page_size,
            'total_objects': self.page.paginator.count,
            'previous_page_number': previous_page_number,
            'next_page_number': next_page_number,
            'next': next_url,
            'previous': previous_url,
            'has_next': self.page.has_next(),
            'has_previous': self.page.has_previous(),
        }