from __future__ import annotations

import pytest

from b2_contact.friction_kernel import (
    CURRENT_SYSTEM_BOUND,
    DUAL_CONTACT_IMPLEMENTED,
    FORMAL_NC19_CREDIT,
    GRASP_SUCCESS_CLAIMED,
    LOCK_IMPLEMENTED,
    NEXT_STAGE_AUTHORIZED,
    PHYSICAL_FRICTION_IDENTIFIED,
    PRODUCTION_CONTACT_BACKEND,
    REGULARIZED_FRICTION_IMPLEMENTED,
    RELEASE_AUTHORIZED,
    SOFT_CAPTURE_IMPLEMENTED,
    FrictionConfig,
)
from b1_contact.contact_kernel import ContactError


def test_only_synthetic_regularized_friction_is_implemented():
    assert REGULARIZED_FRICTION_IMPLEMENTED
    assert not any((
        PHYSICAL_FRICTION_IDENTIFIED, DUAL_CONTACT_IMPLEMENTED,
        SOFT_CAPTURE_IMPLEMENTED, LOCK_IMPLEMENTED, GRASP_SUCCESS_CLAIMED,
    ))


def test_formal_current_production_release_flags_are_false():
    assert not any((
        CURRENT_SYSTEM_BOUND, PRODUCTION_CONTACT_BACKEND, FORMAL_NC19_CREDIT,
        RELEASE_AUTHORIZED, NEXT_STAGE_AUTHORIZED,
    ))


def test_regularization_and_coefficient_must_be_positive():
    with pytest.raises(ContactError):
        FrictionConfig(friction_coefficient=0.0).validated()
    with pytest.raises(ContactError):
        FrictionConfig(tangential_regularization_speed_m_s=0.0).validated()


def test_friction_coefficient_above_one_is_rejected():
    with pytest.raises(ContactError):
        FrictionConfig(friction_coefficient=1.01).validated()
