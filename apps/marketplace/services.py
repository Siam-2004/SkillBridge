"""Job lifecycle.

The rule that shapes this module is: a job cannot become visible unless the
client's *available* balance covers its budget, and publishing must move exactly
that much into *reserved* in the same transaction.  ``publish_job`` therefore
takes the wallet lock before it changes the job's status — if the reservation
fails, the job stays a draft and nothing is half-done.
"""


