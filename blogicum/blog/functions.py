def filter_published(Model):

    return Model.filter(is_published=True)
