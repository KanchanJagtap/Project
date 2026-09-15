"""
ai/pipeline — single-camera end-to-end AI orchestrator package.

Public surface:

    from ai.pipeline import SingleCameraPipeline, FrameResult
"""

from .single_camera_pipeline import FrameResult, SingleCameraPipeline

__all__ = ["FrameResult", "SingleCameraPipeline"]
