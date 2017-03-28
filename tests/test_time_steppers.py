# -*- coding: utf-8 -*-
#
import helpers
import parabolic

from dolfin import (
    set_log_level, WARNING, Expression, FunctionSpace, DirichletBC, Function,
    errornorm, project, plot, interactive, triangle, norm, UnitIntervalMesh,
    pi, inner, grad, dx, ds, UnitSquareMesh, FacetNormal, interval,
    TrialFunction, TestFunction, assemble, KrylovSolver, MPI
    )
import matplotlib.pyplot as plt
import numpy
import pytest
import sympy


# Turn down the log level to only error messages.
set_log_level(WARNING)
# set_log_level(ERROR)
# set_log_level(0)

MAX_DEGREE = 5


def problem_sin1d():
    '''sin-sin example.
    '''
    def mesh_generator(n):
        return UnitIntervalMesh(n)
    x = sympy.DeferredVector('x')
    t = sympy.symbols('t')
    # m = sympy.sin(0.5*pi*t)
    m = sympy.exp(t) - 0.0
    # theta = m * x * (1-x)
    theta = m * sympy.sin(1 * pi * x[0])
    # Produce a matching rhs.
    f_sympy = sympy.diff(theta, t) - sympy.diff(theta, x[0], 2)
    f = Expression(sympy.printing.ccode(f_sympy), degree=MAX_DEGREE, t=0.0)

    class Heat(object):
        '''
        u' = \Delta u + f
        '''
        def __init__(self, V):
            self.sol = Expression(
                    sympy.printing.ccode(theta),
                    degree=MAX_DEGREE,
                    t=0.0,
                    cell=triangle
                    )

            self.V = V
            u = TrialFunction(V)
            v = TestFunction(V)
            self.M = assemble(u * v * dx)
            self.A = assemble(-inner(grad(u), grad(v)) * dx)
            self.f = assemble(f * v * dx)
            self.bcs = DirichletBC(self.V, self.sol, 'on_boundary')
            return

        def eval_alpha_M_beta_F(self, alpha, beta, u, t):
            # Evaluate  alpha * M * u + beta * F(u, t).
            uvec = u.vector()
            return alpha * (self.M * uvec) + beta * (self.A * uvec + self.f)

        def solve_alpha_M_beta_F(self, alpha, beta, b, t):
            # Solve  alpha * M * u + beta * F(u, t) = b  for u.
            A = alpha * self.M + beta * self.A
            rhs = b - beta * self.f
            self.bcs.apply(A, rhs)

            solver = \
                KrylovSolver('gmres', 'ilu') if alpha < 0.0 or beta > 0.0 \
                else KrylovSolver('cg', 'amg')
            solver.parameters['relative_tolerance'] = 1.0e-13
            solver.parameters['absolute_tolerance'] = 0.0
            solver.parameters['maximum_iterations'] = 100
            solver.parameters['monitor_convergence'] = False
            solver.set_operator(A)

            u = Function(self.V)
            solver.solve(u.vector(), rhs)
            return u

    return mesh_generator, theta, Heat, interval


def problem_sinsin():
    '''sin-sin example.
    '''
    def mesh_generator(n):
        return UnitSquareMesh(n, n, 'left/right')
        # return RectangleMesh(1.0, 0.0, 2.0, 1.0, n, n)
    # x, y, t = sympy.symbols('x, y, t')
    x = sympy.DeferredVector('x')
    t = sympy.symbols('t')
    # Choose the solution something that cannot exactly be expressed by
    # polynomials. Choosing the sine here makes all first-order scheme be
    # second-order accurate since d2sin/dt2 = 0 at t=0.
    m = sympy.exp(t) - 0.0
    # m = sympy.sin(0.5*pi*t)
    theta = m * x[0] * (1.0 - x[0]) * x[1] * (1.0 - x[1])
    # theta = m * sympy.sin(1*pi*x) * sympy.sin(1*pi*y)
    rho = 5.0
    cp = 2.0
    kappa = 3.0
    # Produce a matching rhs.
    f_sympy = (
        + rho * cp * sympy.diff(theta, t)
        - sympy.diff(kappa * sympy.diff(theta, x[0]), x[0])
        - sympy.diff(kappa * sympy.diff(theta, x[1]), x[1])
        )
    f = Expression(sympy.printing.ccode(f_sympy), degree=4, t=0.0)

    class Heat(object):
        '''
        u' = \Delta u + f
        '''
        def __init__(self, V):
            self.sol = Expression(
                    sympy.printing.ccode(theta),
                    degree=MAX_DEGREE,
                    t=0.0,
                    cell=triangle
                    )

            self.V = V
            u = TrialFunction(V)
            v = TestFunction(V)
            self.M = assemble(u * v * dx)

            n = FacetNormal(self.V.mesh())
            self.A = assemble(
                - inner(kappa * grad(u), grad(v / (rho * cp))) * dx
                + inner(kappa * grad(u), n) * v / (rho * cp) * ds
                )
            self.f = assemble(f * v / (rho * cp) * dx)

            self.bcs = DirichletBC(self.V, self.sol, 'on_boundary')
            return

        def eval_alpha_M_beta_F(self, alpha, beta, u, t):
            # Evaluate  alpha * M * u + beta * F(u, t).
            uvec = u.vector()
            return alpha * (self.M * uvec) + beta * (self.A * uvec + self.f)

        def solve_alpha_M_beta_F(self, alpha, beta, b, t):
            # Solve  alpha * M * u + beta * F(u, t) = b  for u.
            A = alpha * self.M + beta * self.A
            rhs = b - beta * self.f
            self.bcs.apply(A, rhs)

            solver = \
                KrylovSolver('gmres', 'ilu') if alpha < 0.0 or beta > 0.0 \
                else KrylovSolver('cg', 'amg')
            solver.parameters['relative_tolerance'] = 1.0e-13
            solver.parameters['absolute_tolerance'] = 0.0
            solver.parameters['maximum_iterations'] = 100
            solver.parameters['monitor_convergence'] = False
            solver.set_operator(A)

            u = Function(self.V)
            solver.solve(u.vector(), rhs)
            return u

    return mesh_generator, theta, Heat, triangle


def problem_coscos_cartesian():
    '''cos-cos example. Inhomogeneous boundary conditions.
    '''
    def mesh_generator(n):
        mesh = UnitSquareMesh(n, n, 'left/right')
        # mesh = RectangleMesh(
        #     Point(1.0, 0.0), Point(2.0, 1.0),
        #     n, n, 'left/right'
        #     )
        return mesh
    t = sympy.symbols('t')
    rho = 1.0
    cp = 1.0
    # kappa_sympy = sympy.exp(t)
    kappa_sympy = 1.0
    x = sympy.DeferredVector('x')
    # Choose the solution something that cannot exactly be expressed by
    # polynomials.
    # solution = t * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    # solution = t**2 * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    # solution = t**3 * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    # solution = t**4 * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    # solution = sympy.sin(t) * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    # solution = sympy.cos(t) * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    # solution = sympy.exp(t) * sympy.sin(pi*x[0]) * sympy.sin(pi*x[1])
    solution = \
        sympy.exp(t) * \
        (0.25 - (x[0] - 0.5)**2) * (0.25 - (x[1] - 0.5)**2)
    # solution = sympy.cos(0.5*pi*t) * sympy.sin(pi*x) * sympy.sin(pi*y)
    # solution = \
    #     (sympy.exp(t)) * \
    #     sympy.cos(3*pi*(x[0]-1.0)) * sympy.cos(7*pi*x[1])
    # solution = (1-sympy.cos(t)) * sympy.cos(3*pi*(x-1.0)) * sympy.cos(7*pi*y)
    # solution = sympy.log(1+t) * sympy.cos(3*pi*(x-1.0)) * sympy.cos(7*pi*y)
    # solution = \
    #     sympy.log(2 + t) * \
    #     sympy.cos(pi * (x[0] - 1.0)) * sympy.cos(pi * x[1])
    # Produce a matching rhs.
    f_sympy = (
        rho * cp * sympy.diff(solution, t)
        - sympy.diff(kappa_sympy * sympy.diff(solution, x[0]), x[0])
        - sympy.diff(kappa_sympy * sympy.diff(solution, x[1]), x[1])
        )

    f = Expression(sympy.printing.ccode(f_sympy), degree=MAX_DEGREE, t=0.0)
    kappa = Expression(sympy.printing.ccode(kappa_sympy), degree=1, t=0.0)

    class Heat(object):
        '''
        u' = \Delta u + f
        '''
        def __init__(self, V):
            self.sol = Expression(
                    sympy.printing.ccode(solution),
                    degree=MAX_DEGREE,
                    t=0.0,
                    cell=triangle
                    )

            self.V = V
            u = TrialFunction(V)
            v = TestFunction(V)
            self.M = assemble(u * v * dx)

            n = FacetNormal(self.V.mesh())
            self.A = assemble(
                - inner(kappa * grad(u), grad(v / (rho * cp))) * dx
                + inner(kappa * grad(u), n) * v / (rho * cp) * ds
                )
            self.f = assemble(f * v / (rho * cp) * dx)

            self.bcs = DirichletBC(self.V, self.sol, 'on_boundary')
            return

        def eval_alpha_M_beta_F(self, alpha, beta, u, t):
            # Evaluate  alpha * M * u + beta * F(u, t).
            uvec = u.vector()
            return alpha * (self.M * uvec) + beta * (self.A * uvec + self.f)

        def solve_alpha_M_beta_F(self, alpha, beta, b, t):
            # Solve  alpha * M * u + beta * F(u, t) = b  for u.
            A = alpha * self.M + beta * self.A
            rhs = b - beta * self.f
            self.bcs.apply(A, rhs)

            solver = \
                KrylovSolver('gmres', 'ilu') if alpha < 0.0 or beta > 0.0 \
                else KrylovSolver('cg', 'amg')
            solver.parameters['relative_tolerance'] = 1.0e-13
            solver.parameters['absolute_tolerance'] = 0.0
            solver.parameters['maximum_iterations'] = 100
            solver.parameters['monitor_convergence'] = False
            solver.set_operator(A)

            u = Function(self.V)
            solver.solve(u.vector(), rhs)
            return u

    return mesh_generator, solution, Heat, triangle


# def problem_coscos_cylindrical():
#     '''cos-cos example. Inhomogeneous boundary conditions.
#     '''
#     def mesh_generator(n):
#         mesh = UnitSquareMesh(n, n, 'left/right')
#         # mesh = RectangleMesh(
#         #     Point(1.0, 0.0), Point(2.0, 1.0),
#         #     n, n, 'left/right'
#         #     )
#         return mesh
#
#     t = sympy.symbols('t')
#     rho = 2.0
#     cp = 3.0
#     kappa_sympy = sympy.exp(t)
#
#     # Cylindrical coordinates.
#     x = sympy.DeferredVector('x')
#     # Solution.
#     sol = \
#         (sympy.exp(t) - 1) * sympy.cos(pi * (x[0] - 1)) * sympy.cos(pi * x[1])
#     # theta = sympy.sin(t) * sympy.sin(pi*(x[0]-1)) * sympy.sin(pi*x[1])
#     # theta = sympy.log(2+t) * sympy.cos(pi*(x[0]-1.0)) * sympy.cos(pi*x[1])
#
#     # Convection.
#     b_sympy = (-x[1], x[0] - 1)
#     # b_sympy = (0.0, 0.0)
#
#     # Produce a matching rhs.
#     f_sympy = (
#         + rho * cp * sympy.diff(sol, t)
#         + rho * cp * (
#             + b_sympy[0] * sympy.diff(sol, x[0])
#             + b_sympy[1] * sympy.diff(sol, x[1])
#             )
#         - 1 / x[0] * sympy.diff(x[0]*kappa_sympy * sympy.diff(sol, x[0]), x[0])
#         - sympy.diff(kappa_sympy * sympy.diff(sol, x[1]), x[1])
#         )
#
#     # convert to FEniCS expressions
#     f = Expression(sympy.printing.ccode(f_sympy), degree=MAX_DEGREE, t=0.0)
#     b = Expression(
#             (
#                 sympy.printing.ccode(b_sympy[0]),
#                 sympy.printing.ccode(b_sympy[1])
#             ),
#             degree=1,
#             t=0.0
#             )
#     kappa = Expression(sympy.printing.ccode(kappa_sympy), degree=1, t=0.0)
#
#     class HeatEquation(parabolic.ParabolicProblem):
#         def __init__(self, V):
#             super(HeatEquation, self).__init__()
#             # Define the differential equation.
#             self.V = V
#             self.rho_cp = rho * cp
#             self.sol = Expression(
#                     sympy.printing.ccode(sol),
#                     degree=MAX_DEGREE,
#                     t=0.0,
#                     cell=triangle
#                     )
#             return
#
#         def get_system(self, t):
#             kappa.t = t
#             f.t = t
#             n = FacetNormal(self.V.mesh())
#             u = TrialFunction(self.V)
#             v = TestFunction(self.V)
#             r = Expression('x[0]', degree=1, cell=triangle)
#             # All time-dependent components be set to t.
#             f.t = t
#             b.t = t
#             kappa.t = t
#             F = (
#                 - inner(b, grad(u)) * v * dx
#                 - 1.0 / (rho * cp) * dot(r * kappa * grad(u), grad(v / r)) * dx
#                 + 1.0 / (rho * cp) * dot(r * kappa * grad(u), n) * v / r * ds
#                 + 1.0 / (rho * cp) * f * v * dx
#                 )
#             return assemble(lhs(F)), assemble(rhs(F))
#
#         def get_bcs(self, t):
#             self.sol.t = t
#             return [DirichletBC(self.V, self.sol, 'on_boundary')]
#
#     return mesh_generator, sol, HeatEquation, triangle
#
#
# def problem_stefanboltzmann():
#     '''Heat equation with Stefan-Boltzmann boundary conditions, i.e.,
#     du/dn = u^4 - u_0^4
#     '''
#     def mesh_generator(n):
#         mesh = UnitSquareMesh(n, n, 'left/right')
#         return mesh
#
#     t = sympy.symbols('t')
#     rho = 1.0
#     cp = 1.0
#     kappa = 1.0
#     x = sympy.DeferredVector('x')
#     # Choose the solution something that cannot exactly be expressed by
#     # polynomials.
#     # theta = sympy.sin(t) * sympy.sin(pi*x) * sympy.sin(pi*y)
#     # theta = sympy.cos(0.5*pi*t) * sympy.sin(pi*x) * sympy.sin(pi*y)
#     # theta = (sympy.exp(t)-1) * sympy.cos(3*pi*(x-1.0)) * sympy.cos(7*pi*y)
#     # theta = (1-sympy.cos(t)) * sympy.cos(3*pi*(x-1.0)) * sympy.cos(7*pi*y)
#     # theta = sympy.log(1+t) * sympy.cos(3*pi*(x-1.0)) * sympy.cos(7*pi*y)
#     theta = sympy.log(2 + t) * sympy.cos(pi * x[0]) * sympy.cos(pi * x[1])
#     # Produce a matching rhs.
#     f_sympy = (
#         + rho * cp * sympy.diff(theta, t)
#         - sympy.diff(kappa * sympy.diff(theta, x[0]), x[0])
#         - sympy.diff(kappa * sympy.diff(theta, x[1]), x[1])
#         )
#     # Produce a matching u0.
#     # u_0^4 = u^4 - du/dn
#     # ONLY WORKS IF du/dn==0.
#     u0 = theta
#     # convert to FEniCS expressions
#     f = Expression(sympy.printing.ccode(f_sympy), degree=MAX_DEGREE, t=0.0)
#     u0 = Expression(sympy.printing.ccode(u0), degree=MAX_DEGREE, t=0.0)
#
#     class HeatEquation(parabolic.ParabolicProblem):
#         def __init__(self, V):
#             super(HeatEquation, self).__init__()
#             # Define the differential equation.
#             self.V = V
#             self.rho_cp = rho * cp
#             self.sol = Expression(
#                     sympy.printing.ccode(theta),
#                     degree=MAX_DEGREE,
#                     t=0.0,
#                     cell=triangle
#                     )
#             return
#
#         def get_system(self, t):
#             u0.t = t
#             f.t = t
#             u = TrialFunction(self.V)
#             v = TestFunction(self.V)
#             F = - 1.0 / (rho * cp) * kappa * dot(grad(u), grad(v)) * dx \
#                 + 1.0 / (rho * cp) * kappa * (u*u*u*u - u0*u0*u0*u0) * v * ds \
#                 + 1.0 / (rho * cp) * f * v * dx
#             return assemble(lhs(F)), assemble(rhs(F))
#
#         def get_bcs(self, t):
#             self.sol.t = t
#             return [DirichletBC(self.V, self.sol, 'on_boundary')]
#
#     return mesh_generator, theta, HeatEquation, triangle


@pytest.mark.parametrize(
    'method', [
        parabolic.ImplicitEuler
        ])
@pytest.mark.parametrize(
    'problem', [
        problem_sin1d,
        # problem_sinsin,
        # problem_coscos_cartesian,
        # problem_coscos_cylindrical,
        # problem_stefanboltzmann
        ])
def test_temporal_order(problem, method):
    # TODO add test for spatial order
    mesh_sizes = [16, 32, 64]
    Dt = [0.5**k for k in range(2)]
    errors = _compute_time_errors(problem, method, mesh_sizes, Dt)

    # Error bounds are of the form
    #
    #     ||E|| < C t_n (C1 dt^k + C2 dh^l).
    #
    # Hence, divide the error by t_n (=dt in this case).
    errors /= Dt

    # numerical orders of convergence
    orders = helpers._compute_numerical_order_of_convergence(Dt, errors.T).T

    # The test is considered passed if the numerical order of convergence
    # matches the expected order in at least the first step in the coarsest
    # spatial discretization, and is not getting worse as the spatial
    # discretizations are refining.
    tol = 0.1
    assert (orders[:, 0] > method.order - tol).all()
    return


def _compute_time_errors(problem, method, mesh_sizes, Dt, plot_error=False):
    mesh_generator, solution, ProblemClass, cell_type = problem()
    # Translate data into FEniCS expressions.
    fenics_sol = Expression(
            sympy.printing.ccode(solution),
            degree=MAX_DEGREE,
            t=0.0
            )
    # Compute the problem
    errors = numpy.empty((len(mesh_sizes), len(Dt)))
    # Create initial state.
    # Deepcopy the expression into theta0. Specify the cell to allow for
    # more involved operations with it (e.g., grad()).
    theta0 = Expression(
            fenics_sol.cppcode,
            degree=MAX_DEGREE,
            t=0.0
            )
    for k, mesh_size in enumerate(mesh_sizes):
        mesh = mesh_generator(mesh_size)

        # Choose the function space such that the exact solution can be
        # represented as well as possible.
        V = FunctionSpace(mesh, 'CG', 4)

        theta_approx = Function(V)
        theta0p = project(theta0, V)

        stepper = method(ProblemClass(V))
        if plot_error:
            error = Function(V)
        for j, dt in enumerate(Dt):
            # TODO We are facing a little bit of a problem here, being the fact
            # that the time stepper only accept elements from V as u0.  In
            # principle, though, this isn't necessary or required. We could
            # allow for arbitrary expressions here, but then the API would need
            # changing for problem.lhs(t, u).  Think about this.
            theta_approx.assign(stepper.step(theta0p, 0.0, dt))
            fenics_sol.t = dt

            # NOTE
            # When using errornorm(), it is quite likely to see a good part of
            # the error being due to the spatial discretization.  Some analyses
            # "get rid" of this effect by (sometimes implicitly) projecting the
            # exact solution onto the discrete function space.

            errors[k][j] = errornorm(fenics_sol, theta_approx)
            if plot_error:
                error.assign(project(fenics_sol - theta_approx, V))
                plot(error, title='error (dt=%e)' % dt)
                interactive()
    return errors


def _check_spatial_order(problem, method):
    mesh_generator, solution, weak_F = problem()

    # Translate data into FEniCS expressions.
    fenics_sol = Expression(
            sympy.printing.ccode(solution['value']),
            degree=solution['degree'],
            t=0.0
            )

    # Create initial solution.
    theta0 = Expression(
            fenics_sol.cppcode,
            degree=solution['degree'],
            t=0.0,
            cell=triangle
            )

    # Estimate the error component in space.
    # Leave out too rough discretizations to avoid showing spurious errors.
    N = [2**k for k in range(2, 8)]
    dt = 1.0e-8
    Err = []
    H = []
    for n in N:
        mesh = mesh_generator(n)
        H.append(MPI.max(mesh.hmax()))
        V = FunctionSpace(mesh, 'CG', 5)
        # Create boundary conditions.
        fenics_sol.t = dt
        # bcs = DirichletBC(V, fenics_sol, 'on_boundary')
        # Create initial state.
        theta_approx = method(
                V,
                weak_F,
                theta0,
                0.0, dt,
                bcs=[solution],
                tol=1.0e-12,
                verbose=True
                )
        # Compute the error.
        fenics_sol.t = dt
        Err.append(
            errornorm(fenics_sol, theta_approx) / norm(fenics_sol, mesh=mesh)
            )
        print('n: %d    error: %e' % (n, Err[-1]))

    # Plot order curves for comparison.
    for order in [2, 3, 4]:
        plt.loglog(
            [H[0], H[-1]],
            [Err[0], Err[0] * (H[-1] / H[0]) ** order],
            color='0.5'
            )
    # Finally, the actual data.
    plt.loglog(H, Err, '-o')
    plt.xlabel('h_max')
    plt.ylabel('||u-u_h|| / ||u||')
    plt.show()
    return


if __name__ == '__main__':
    # For debugging purposes, show some info.
    mesh_sizes = [16, 32]
    Dt = [0.5**k for k in range(15)]
    errors = _compute_time_errors(
        # problem_sin1d,
        # problem_sinsin,
        problem_coscos_cartesian,
        # parabolic.Dummy,
        # parabolic.ExplicitEuler,
        # parabolic.ImplicitEuler,
        parabolic.Trapezoidal,
        mesh_sizes, Dt,
        )

    helpers.show_timeorder_info(Dt, mesh_sizes, {'theta': errors})
