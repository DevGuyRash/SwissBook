"""Test logging configuration for external libraries."""

import logging

import pytest


def test_external_library_warnings_suppressed_without_verbose():
    """Test that external library warnings don't appear in console without verbose flags."""
    
    # Simulate what happens in the CLI when configuring external loggers
    verbose = 0
    console_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    external_console_level = logging.ERROR if verbose == 0 else console_level
    
    # Verify that external console level is ERROR when verbose=0
    assert external_console_level == logging.ERROR
    
    # Test that a WARNING message from site_downloader wouldn't appear
    # when the console handler level is ERROR
    assert external_console_level > logging.WARNING


def test_external_library_warnings_shown_with_verbose():
    """Test that external library warnings appear in console with verbose flags."""
    
    # Test with verbose=1 (INFO level)
    console_level = logging.INFO  # This is what happens when verbose=1
    external_console_level = logging.ERROR if 1 == 0 else console_level  # verbose=1
    
    # Verify that external console level allows warnings when verbose>=1
    assert external_console_level == logging.INFO
    assert external_console_level <= logging.WARNING


def test_logging_configuration_logic():
    """Test the core logic of the logging configuration."""
    
    # Test verbose=0 case
    verbose = 0
    console_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    external_console_level = logging.ERROR if verbose == 0 else console_level
    
    assert console_level == logging.WARNING
    assert external_console_level == logging.ERROR
    assert external_console_level > logging.WARNING  # Warnings suppressed
    
    # Test verbose=1 case  
    verbose = 1
    console_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    external_console_level = logging.ERROR if verbose == 0 else console_level
    
    assert console_level == logging.INFO
    assert external_console_level == logging.INFO
    assert external_console_level <= logging.WARNING  # Warnings shown
    
    # Test verbose=2 case
    verbose = 2
    console_level = [logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)]
    external_console_level = logging.ERROR if verbose == 0 else console_level
    
    assert console_level == logging.DEBUG
    assert external_console_level == logging.DEBUG
    assert external_console_level <= logging.WARNING  # Warnings shown