{% extends "harvester.tpl" %}

{% block logs %}
    {% for file in logfiles %}
        "/home/xavier/.quantrade/log/{{ file.name }}",
    {% endfor %}
    "/home/xavier/.quantrade/log/{{ last }}"
{% endblock %}
