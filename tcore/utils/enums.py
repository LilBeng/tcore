import operator
from enum import Enum


class Operator(Enum):
    LT = operator.lt  # Less Than — меньше (<)
    LE = operator.le  # Less or Equal — меньше или равно (<=)
    GT = operator.gt  # Greater Than — больше (>)
    GE = operator.ge  # Greater or Equal — больше или равно (>=)
    EQ = operator.eq  # Equal — равно (==)
    NE = operator.ne  # Not Equal — не равно (!=)
