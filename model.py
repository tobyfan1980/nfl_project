import math

class NFLModel1:
    def __init__(self):
        pass

    def offensive_rating(self, yards: int, points: int) -> float:
        """
        Offensive rating is a measure of a team's offensive performance.
        It is calculated by taking the square root of the team's yards per game plus 40,
        multiplying by 2, and adding the square root of the team's points per game multiplied by 5,
        multiplied by the square root of 2, multiplied by 0.6.

        Args:
            yards: The number of yards the team has gained.
            points: The number of points the team has scored.

        Returns:
            The offensive rating of the team.
        """
        return math.sqrt(yards / 5 +40) * 2 + \
            math.sqrt(points * 5 * math.sqrt(2) * 0.6) * 5

    def defensive_rating(self, yards_op: int, points_op: int, to_op: int) -> float:
        """
        Defensive rating is a measure of a team's defensive performance.
        It is calculated by taking the opposing team's yards per game divided by 72,
        subtracting (25 * turnovers + 72) / 72, and adding 1.3 * points per game divided by 11.

        Args:
            yards_op: The number of yards the opposing team has gained.
            points_op: The number of points the opposing team has scored.
            to_op: The number of turnovers the opposing team has committed.

        Returns:
            The defensive rating of the team.
        """
        return yards_op / 72 - (25 * to_op + 72) / 72  + 1.3 * points_op / 11

    