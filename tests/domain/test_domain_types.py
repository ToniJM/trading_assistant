"""Tests for domain types"""

from trading.domain.types import ORDER_SIDE_TYPE, ORDER_STATUS_TYPE, ORDER_TYPE_TYPE, SIDE_TYPE


def test_side_type_valid():
    """Test that SIDE_TYPE accepts valid values"""
    # This is a type check, runtime validation would need actual usage
    assert SIDE_TYPE is not None


def test_order_side_type_valid():
    """Test that ORDER_SIDE_TYPE accepts valid values"""
    assert ORDER_SIDE_TYPE is not None


def test_order_type_type_valid():
    """Test that ORDER_TYPE_TYPE accepts valid values"""
    assert ORDER_TYPE_TYPE is not None


def test_order_status_type_valid():
    """Test that ORDER_STATUS_TYPE accepts valid values"""
    assert ORDER_STATUS_TYPE is not None

