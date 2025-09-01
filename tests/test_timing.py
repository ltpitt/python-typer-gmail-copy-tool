import pytest
import time
from unittest.mock import patch, MagicMock
from gmail_copy_tool.utils.timing import timing


class TestTiming:
    """Test the timing decorator."""

    def test_timing_decorator_basic(self, capsys):
        """Test that timing decorator measures and prints execution time."""
        
        @timing
        def test_function():
            time.sleep(0.01)  # Small delay for measurable time
            return "result"
        
        result = test_function()
        
        assert result == "result"
        
        captured = capsys.readouterr()
        assert "[Timing] test_function took" in captured.out
        assert "seconds." in captured.out

    def test_timing_decorator_with_args(self, capsys):
        """Test timing decorator with function arguments."""
        
        @timing
        def add_numbers(a, b, multiply_by=1):
            return (a + b) * multiply_by
        
        result = add_numbers(2, 3, multiply_by=4)
        
        assert result == 20
        
        captured = capsys.readouterr()
        assert "[Timing] add_numbers took" in captured.out

    def test_timing_decorator_with_exception(self, capsys):
        """Test timing decorator when function raises exception."""
        
        @timing
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()
        
        captured = capsys.readouterr()
        # The current implementation doesn't print timing on exception
        # This is expected behavior - timing is only shown on successful completion
        # If we wanted to show timing on exceptions, we'd need to modify the decorator
        assert captured.out == ""  # No timing output expected on exception

    def test_timing_decorator_preserves_function_metadata(self):
        """Test that timing decorator preserves function metadata."""
        
        @timing
        def documented_function():
            """This function has documentation."""
            return "test"
        
        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This function has documentation."

    def test_timing_precision(self, capsys):
        """Test that timing shows appropriate precision."""
        
        @timing
        def quick_function():
            pass
        
        quick_function()
        
        captured = capsys.readouterr()
        # Should show time with 2 decimal places
        import re
        timing_pattern = r"\[Timing\] quick_function took \d+\.\d{2} seconds\."
        assert re.search(timing_pattern, captured.out)

    @patch('gmail_copy_tool.utils.timing.time.perf_counter')
    def test_timing_calculation(self, mock_perf_counter, capsys):
        """Test that timing calculation is correct."""
        # Mock perf_counter to return specific values
        mock_perf_counter.side_effect = [10.0, 12.5]  # 2.5 seconds difference
        
        @timing
        def timed_function():
            return "test"
        
        result = timed_function()
        
        assert result == "test"
        captured = capsys.readouterr()
        assert "2.50 seconds" in captured.out

    def test_timing_multiple_calls(self, capsys):
        """Test timing decorator with multiple function calls."""
        
        @timing
        def counter_function(count):
            return count * 2
        
        result1 = counter_function(5)
        result2 = counter_function(10)
        
        assert result1 == 10
        assert result2 == 20
        
        captured = capsys.readouterr()
        # Should have two timing outputs
        timing_lines = [line for line in captured.out.split('\n') if '[Timing]' in line]
        assert len(timing_lines) == 2
        assert all('counter_function took' in line for line in timing_lines)

    def test_timing_with_complex_return(self, capsys):
        """Test timing decorator with complex return values."""
        
        @timing
        def complex_function():
            return {"data": [1, 2, 3], "status": "success"}
        
        result = complex_function()
        
        assert result == {"data": [1, 2, 3], "status": "success"}
        
        captured = capsys.readouterr()
        assert "[Timing] complex_function took" in captured.out