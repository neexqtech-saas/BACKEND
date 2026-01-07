from django.shortcuts import get_object_or_404
from django.db import models

def update_model_instance(instance, data: dict):
    """
    Update model instance fields dynamically.
    Handles ForeignKey, ManyToMany, and normal fields.
    """
    errors = {}
    updated_fields = []

    for field, value in data.items():
        try:
            field_obj = instance._meta.get_field(field)

            # ✅ If ForeignKey
            if isinstance(field_obj, models.ForeignKey):
                related_model = field_obj.related_model
                related_instance = get_object_or_404(related_model, id=value)
                setattr(instance, field, related_instance)
                updated_fields.append(field)

            # ✅ If ManyToMany
            elif isinstance(field_obj, models.ManyToManyField):
                related_model = field_obj.related_model
                instances = related_model.objects.filter(id__in=value)
                getattr(instance, field).set(instances)
                updated_fields.append(field)

            # ✅ Normal fields
            else:
                setattr(instance, field, value)
                updated_fields.append(field)

        except Exception as e:
            errors[field] = str(e)

    instance.save()
    return {"updated": updated_fields, "errors": errors}
