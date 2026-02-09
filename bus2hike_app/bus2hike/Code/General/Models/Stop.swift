//
//  BusStop.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//

import Foundation
import MapKit

struct Stop: Identifiable, Equatable {
   static func == (lhs: Stop, rhs: Stop) -> Bool {
       lhs.id == rhs.id &&
       lhs.name == rhs.name &&
       lhs.location.latitude == rhs.location.latitude &&
       lhs.location.longitude == rhs.location.longitude
   }
   
    let id: Int
    let name: String
    let location: CLLocationCoordinate2D
}

extension Stop {
    init(dto: StopDTO) {
        self.id = dto.id
        self.name = dto.name
        self.location = CLLocationCoordinate2D(
            latitude: dto.geometry.coordinates[1],
            longitude: dto.geometry.coordinates[0]
        )
    }
}

