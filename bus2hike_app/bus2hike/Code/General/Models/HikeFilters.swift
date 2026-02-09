//
//  TrailFilters.swift
//  bus2hike
//
//  Created by Antonia Stieger on 30.01.26.
//


struct HikeFilters {
    var radiusKm: Double = 10
    var difficulty: Difficulty = .any
    var maxDuration: Duration = .init(hours: 5, minutes: 0)
    var isCircular: Bool = false
}

enum Difficulty: String, CaseIterable, Identifiable {
    case any = "Any"
    case easy = "Easy"
    case moderate = "Moderate"
    case hard = "Hard"
    case veryHard = "Very Hard"
    case extreme = "Extreme"

    var id: String { rawValue }
}

struct Duration: Hashable {
    var hours: Int
    var minutes: Int
}
