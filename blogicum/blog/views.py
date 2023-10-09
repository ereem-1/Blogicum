from django.db.models import Count
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, reverse
from django.utils import timezone
from django.db.models import Q
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from .mixins import PaginatorMixin
from .functions import filter_published
from blog.models import Category, Comment, Post, User
from .forms import CommentForm, PostForm, UserForm

POSTS_LIMIT = 10

IS_PUBLISHED_TRUE = (Q(pub_date__lte=timezone.now())
                     & Q(is_published=True)
                     & Q(category__is_published=True))


class IndexListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = POSTS_LIMIT
    queryset = Post.objects.select_related(
        'location', 'author', 'category'
    ).filter(IS_PUBLISHED_TRUE).order_by('-pub_date').annotate(
        comment_count=Count('post_comments'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_count'] = Comment.objects.annotate(Count('id'))
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'

    def dispatch(self, request, *args, **kwargs):
        instance = get_object_or_404(
            Post.objects.select_related("category", "location"
                                        ),
            pk=kwargs['pk']
        )
        if instance.author != request.user:
            if (
                not instance.is_published
                or not instance.category.is_published
                or instance.pub_date > timezone.now()
            ):
                raise Http404('Пост не существует или не опубликован')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            form=CommentForm(),
            comments=self.object.post_comments.select_related('author'),
            **kwargs,
        )


class CategoryListView(PaginatorMixin, ListView):
    model = Post
    paginate_by = POSTS_LIMIT
    template_name = 'blog/category.html'
    slug_url_kwarg = 'category_slug'

    def get_queryset(self):
        category = get_object_or_404(
            Category,
            slug=self.kwargs['category_slug']
        )
        if not category.is_published:
            raise Http404('Категория не существует или не опубликована')
        return self.model.objects.annotate(
            comment_count=Count('post_comments')).filter(
            IS_PUBLISHED_TRUE,
            category__slug=self.kwargs['category_slug']
        ).order_by('-pub_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = Category.objects.get(
            slug=self.kwargs['category_slug']
        )
        return context


class ProfileListView(ListView):
    model = User
    template_name = 'blog/profile.html'
    ordering = '-pub_date'
    paginate_by = POSTS_LIMIT

    def get_queryset(self):
        self.author = get_object_or_404(
            User,
            username=self.kwargs['username']
        )

        if self.author != self.request.user:
            return filter_published(Post.objects.filter(
                author=self.author,
            )).order_by(
                '-pub_date').annotate(comment_count=Count('post_comments'))

        return Post.objects.filter(
            author=self.author
        ).order_by('-pub_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = get_object_or_404(
            User,
            username=self.kwargs['username']
        )
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = 'blog/user.html'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.kwargs['username']},
        )


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_success_url(self):
        slug = self.request.user.username
        return reverse('blog:profile', kwargs={'username': slug})

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'pk'

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['pk']},
        )

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.kwargs['pk']
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        instance = get_object_or_404(Post, pk=self.kwargs['pk'])
        if instance.author != request.user:
            return redirect('blog:post_detail', self.kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    success_url = reverse_lazy('blog:index')

    def dispatch(self, request, *args, **kwargs):
        instance = get_object_or_404(Post, pk=kwargs['pk'])
        if instance.author != request.user:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm
    queryset = Comment.objects
    pk_url_kwarg = 'pk'
    posts = None

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.posts.pk},
        )

    def dispatch(self, request, *args, **kwargs):
        self.posts = get_object_or_404(Post, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.posts
        return super().form_valid(form)


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        instance = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if instance.author != request.user:
            return redirect('blog:post_detail', instance.post_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['pk']},
        )


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def dispatch(self, request, *args, **kwargs):
        instance = get_object_or_404(Comment, pk=kwargs['comment_id'])
        if instance.author != request.user:
            return redirect('blog:post_detail', instance.post_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['pk']},
        )
