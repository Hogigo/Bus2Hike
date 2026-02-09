//
//  Trail.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import Foundation
import MapKit


struct Hike: Identifiable {
   let id: Int
   let odh_id: String

   let name: String
   let description: String

   let difficulty: String?
   let length_km: Double?
   let duration_minutes: Int?
   let elevation_gain_m: Int?
   let elevation_loss_m: Int?
   let circular: Bool
   let coordinates: [CLLocationCoordinate2D]
}

extension Hike {
    var title: String {
        odh_id.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var shortDescription: String {
       "\(difficulty ?? "Unknown") · \(length_km ?? 0, default: "%.1f") km · \(duration_minutes ?? 0) min"
    }
   
   var longDescription: String {
       description
   }

    var imageName: String {
        "hike_placeholder" // add to Assets
    }
}

extension Hike {
    var midCoordinate: CLLocationCoordinate2D? {
        guard !coordinates.isEmpty else { return nil }
        
        let midIndex = coordinates.count / 2
        return coordinates[midIndex]
    }
}

extension Hike {
   struct HikeDTO: Decodable {
      let id: Int
      let odh_id: String
      let name: String
      let description: String
      let difficulty: String?
      let length_km: Double?
      let duration_minutes: Int?
      let elevation_gain_m: Int?
      let elevation_loss_m: Int?
      let circular: Bool
      let coordinates: [CoordinateDTO]
   }
}
