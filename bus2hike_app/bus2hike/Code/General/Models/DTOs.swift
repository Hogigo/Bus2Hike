//
//  DTOs.swift
//  bus2hike
//
//  Created by Antonia Stieger on 03.02.26.
//

import Foundation

struct FeatureCollectionDTO: Decodable {
    let type: String
    let features: [FeatureDTO]
}

struct FeatureDTO: Decodable {
    let type: String
    let properties: PropertiesDTO
    let geometry: GeometryDTO
}

struct PropertiesDTO: Decodable {
    let path_id: Int
    let total_distance_km: Double
    let edge_ids: [Int]
    let node_sequence: [Int]

    let name: String
    let description: String
}

struct GeometryDTO: Decodable {
    let type: String
    let coordinates: [[Double]] // Each coordinate is [lon, lat, elevation]
}

struct StopDTO: Decodable {
    let id: Int
    let name: String
    let geometry: StopGeometryDTO
}

struct StopGeometryDTO: Decodable {
    let type: String
    let coordinates: [Double]
}

struct HikeDTO: Decodable {
   let id: Int
   let odh_id: String
   let difficulty: String?
   let length_km: Double?
   let duration_minutes: Int?
   let elevation_gain_m: Int?
   let elevation_loss_m: Int?
   let circular: Bool
   let coordinates: [CoordinateDTO]
}

struct CoordinateDTO: Decodable {
   let latitude: Double
   let longitude: Double
}
