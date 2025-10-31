import time


class BaseAbortionCondition:
    abortion_parameter: int
    msg: str

    def __init__(self, abortion_parameter: int):
        self.abortion_parameter = abortion_parameter
        self.msg = "not implemented"

    def should_abort(
            self,
            iteration: int,
            best_iteration: int,
            start_time: int,
            best_sol_time: int
    ) -> bool:
        """
        Evaluate whether the abortion condition is met.
        :param best_sol_time: Time of best found solution
        :param iteration: Current iteration of KGLS.
        :param best_iteration: Iteration of found best solution
        :param start_time: Algorithm start time (for time-based conditions).
        :return: Boolean indicating whether to stop.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class MaxIterationsCondition(BaseAbortionCondition):
    def __init__(self, abortion_parameter: int):
        super().__init__(abortion_parameter)
        self.msg = f"Stops after {abortion_parameter} iterations."

    def should_abort(
            self,
            iteration: int,
            best_iteration: int,
            start_time: int,
            best_sol_time: int
    ) -> bool:
        return iteration >= self.abortion_parameter


class IterationsWithoutImprovementCondition(BaseAbortionCondition):
    def __init__(self, abortion_parameter: int):
        super().__init__(abortion_parameter)
        self.msg = f"Stops after {abortion_parameter} iterations without improvement."

    def should_abort(
            self,
            iteration: int,
            best_iteration: int,
            start_time: int,
            best_sol_time: int
    ) -> bool:
        return iteration - best_iteration >= self.abortion_parameter


class MaxRuntimeCondition(BaseAbortionCondition):
    def __init__(self, abortion_parameter: int):
        super().__init__(abortion_parameter)
        self.msg = f"Stops after {abortion_parameter} seconds."

    def should_abort(
            self,
            iteration: int,
            best_iteration: int,
            start_time: int,
            best_sol_time: int
    ) -> bool:
        elapsed_time = time.process_time() - start_time
        return elapsed_time >= self.abortion_parameter


class RuntimeWithoutImprovementCondition(BaseAbortionCondition):
    def __init__(self, abortion_parameter: int):
        super().__init__(abortion_parameter)
        self.msg = f"Stops after {abortion_parameter} seconds without improvement."

    def should_abort(
            self,
            iteration: int,
            best_iteration: int,
            start_time: int,
            best_sol_time: int
    ) -> bool:
        elapsed_time = time.time() - best_sol_time
        return elapsed_time >= self.abortion_parameter
