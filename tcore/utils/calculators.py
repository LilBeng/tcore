# def aggregate_to_candles(self, ticks: List[TradeTick], interval_seconds: int = 60) -> List[CVD]:
#     """Агрегирует тики в свечи и возвращает CVD для каждой свечи"""
#     if not ticks:
#         return []
#
#     sorted_ticks = sorted(ticks, key=lambda x: x.timestamp)
#
#     from collections import defaultdict
#     groups = defaultdict(list)
#
#     for tick in sorted_ticks:
#         # Округляем до начала интервала
#         interval_start = tick.timestamp.replace(
#             second=(tick.timestamp.second // interval_seconds) * interval_seconds,
#             microsecond=0
#         )
#         groups[interval_start].append(tick)
#
#     result = []
#
#     for interval_start in sorted(groups.keys()):
#         interval_delta = Decimal('0')
#         symbol = groups[interval_start][0].symbol
#
#         for tick in groups[interval_start]:
#             interval_delta += tick.delta
#
#         self._cvd += interval_delta
#
#         result.append(CVD(
#             symbol=symbol,
#             timestamp=interval_start,
#             value=self._cvd,
#             delta=interval_delta
#         ))
#
#     return result