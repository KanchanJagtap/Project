import {
  SystemHealthResponse,
  ProcessingOverviewResponse,
  CamerasListResponse,
  ProcessingStatusResponse,
  VehicleHistoryResponse,
} from './types';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '/api') {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Not found');
      }
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  // System & Overview
  async getSystemHealth(): Promise<SystemHealthResponse> {
    return this.fetch<SystemHealthResponse>('/system/health');
  }

  async getProcessingOverview(): Promise<ProcessingOverviewResponse> {
    return this.fetch<ProcessingOverviewResponse>('/processing/overview');
  }

  // Cameras & Processing
  async getCamerasList(): Promise<CamerasListResponse> {
    return this.fetch<CamerasListResponse>('/processing/cameras');
  }

  async getCameraStatus(cameraId: string): Promise<ProcessingStatusResponse> {
    return this.fetch<ProcessingStatusResponse>(`/processing/status?camera_id=${encodeURIComponent(cameraId)}`);
  }

  // Vehicles
  async getVehicleHistory(plate: string): Promise<VehicleHistoryResponse> {
    return this.fetch<VehicleHistoryResponse>(`/vehicles/${encodeURIComponent(plate)}/history`);
  }
}

export const api = new ApiClient();
