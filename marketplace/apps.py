from django.apps import AppConfig
import copy


class MarketplaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketplace'

    def ready(self):
        # Import signals to register them
        from . import signals
        # Python 3.14 compatibility patch for Django Template Context copy
        try:
            from django.template import context

            def _patched_basecontext_copy(self):
                cls = self.__class__
                duplicate = cls.__new__(cls)
                duplicate.dicts = self.dicts[:]
                return duplicate

            def _patched_context_copy(self):
                cls = self.__class__
                duplicate = cls.__new__(cls)
                duplicate.dicts = self.dicts[:]
                duplicate.autoescape = getattr(self, 'autoescape', True)
                duplicate.use_l10n = getattr(self, 'use_l10n', None)
                duplicate.use_tz = getattr(self, 'use_tz', None)
                duplicate.template_name = getattr(self, 'template_name', None)
                if hasattr(self, 'render_context'):
                    duplicate.render_context = copy.copy(self.render_context)
                return duplicate

            def _patched_requestcontext_copy(self):
                cls = self.__class__
                duplicate = cls.__new__(cls)
                duplicate.dicts = self.dicts[:]
                duplicate.autoescape = getattr(self, 'autoescape', True)
                duplicate.use_l10n = getattr(self, 'use_l10n', None)
                duplicate.use_tz = getattr(self, 'use_tz', None)
                duplicate.template_name = getattr(self, 'template_name', None)
                if hasattr(self, 'render_context'):
                    duplicate.render_context = copy.copy(self.render_context)
                duplicate.request = getattr(self, 'request', None)
                duplicate._processors_index = getattr(self, '_processors_index', len(duplicate.dicts))
                return duplicate

            context.BaseContext.__copy__ = _patched_basecontext_copy
            context.Context.__copy__ = _patched_context_copy
            context.RequestContext.__copy__ = _patched_requestcontext_copy
        except Exception:
            pass
