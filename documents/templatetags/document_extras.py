from django import template

register = template.Library()


STATUS_DATA = {
    "submitted": ("Submitted", "bg-[#eaf4ff] text-[#0067c0]", "w-1/10"),
    "under_registry_review": ("Under Review", "bg-[#fef3c7] text-[#92400e]", "w-2/10"),
    "registered": ("Registered", "bg-[#e0f2fe] text-[#0369a1]", "w-3/10"),
    "forwarded_to_dept": ("Forwarded to Dept", "bg-[#fff7ed] text-[#c43e1c]", "w-4/10"),
    "under_dept_review": ("Dept Review", "bg-[#f3e8ff] text-[#6b21a8]", "w-5/10"),
    "awaiting_director": ("Awaiting Director", "bg-[#fce7f3] text-[#9d174d]", "w-6/10"),
    "approved": ("Approved", "bg-[#ecfdf3] text-[#107c41]", "w-7/10"),
    "returned_to_registry": ("Returned to Registry", "bg-[#dbeafe] text-[#1e40af]", "w-8/10"),
    "ready_for_collection": ("Ready for Collection", "bg-[#d1fae5] text-[#065f46]", "w-9/10"),
    "collected": ("Collected", "bg-[#f3f4f6] text-[#374151]", "w-full"),
}

STATUS_ORDER = [
    "submitted", "under_registry_review", "registered", "forwarded_to_dept",
    "under_dept_review", "awaiting_director", "approved",
    "returned_to_registry", "ready_for_collection", "collected",
]


@register.filter
def status_color(status):
    data = STATUS_DATA.get(status)
    return data[1] if data else "bg-gray-100 text-gray-800"


@register.filter
def status_label(status):
    data = STATUS_DATA.get(status)
    return data[0] if data else status


@register.filter
def progress_width(status):
    data = STATUS_DATA.get(status)
    return data[2] if data else "w-0"


@register.filter
def completed_statuses(status):
    if status not in STATUS_ORDER:
        return []
    idx = STATUS_ORDER.index(status)
    return STATUS_ORDER[:idx + 1]
