# -*- coding: utf-8 -*-
#
'''
Helper functions for PDE consistency tests.
'''
from __future__ import print_function

import warnings

# pylint: disable=import-error
from dolfin import (
    Expression, assemble, FunctionSpace, interpolate, plot,
    errornorm, dx, Function, VectorFunctionSpace, DirichletBC, project
    )
import matplotlib.pyplot as plt
import numpy
import sympy


def _truncate_degree(degree, max_degree=10):
    if degree > max_degree:
        warnings.warn(
            'Expression degree (%r) > maximum degree (%d). Truncating.'
            % (degree, max_degree)
            )
        return max_degree
    return degree


def show_timeorder_info(Dt, mesh_sizes, errors):
    '''Performs consistency check for the given problem/method combination and
    show some information about it. Useful for debugging.
    '''
    # Error bounds are of the form
    #
    #     ||E|| < C t_n (C1 dt^k + C2 dh^l).
    #
    # Hence, divide the error by t_n (=dt in this case).
    # Compute the numerical order of convergence.
    errors = {key: errors[key] / Dt for key in errors}

    orders = {
        key: compute_numerical_order_of_convergence(Dt, errors[key].T).T
        for key in errors
        }

    # Print the data to the screen
    for i, mesh_size in enumerate(mesh_sizes):
        print()
        print('Mesh size %d:' % mesh_size)
        print('dt = %e' % Dt[0])
        for label, e in errors.items():
            print('   err_%s / dt = %e' % (label, e[i][0]))
        print()
        for j in range(len(Dt) - 1):
            print('                 ')
            for label, o in orders.items():
                print('   ord_%s      = %e' % (label, o[i][j]))
            print()
            print('dt = %e' % Dt[j+1])
            for label, e in errors.items():
                print('   err_%s / dt = %e' % (label, e[i][j+1]))
            print()

    # Create a figure
    for label, err in errors.items():
        plt.figure()
        # ax = plt.axes()
        # Plot the actual data.
        for i, mesh_size in enumerate(mesh_sizes):
            plt.loglog(Dt, err[i], '-o', label=mesh_size)
        # Compare with order curves.
        plt.autoscale(False)
        e0 = err[-1][0]
        for o in range(7):
            plt.loglog(
                    [Dt[0], Dt[-1]],
                    [e0, e0 * (Dt[-1] / Dt[0]) ** o],
                    color='0.7'
                    )
        plt.xlabel('dt')
        plt.ylabel('||%s-%s_h|| / dt' % (label, label))
        # plt.title('Method: %s' % method['name'])
        plt.legend()
    plt.show()
    return


def compute_numerical_order_of_convergence(Dt, errors):
    return numpy.array([
        # pylint: disable=no-member
        numpy.log(errors[k] / errors[k+1]) / numpy.log(Dt[k] / Dt[k+1])
        for k in range(len(Dt)-1)
        ])


def _assert_time_order(problem, MethodClass):
    mesh_sizes = [8, 16, 32]
    Dt = [0.5**k for k in range(2)]
    errors = compute_time_errors(problem, MethodClass, mesh_sizes, Dt)
    orders = {
        key: compute_numerical_order_of_convergence(Dt, errors[key].T).T
        for key in errors
        }
    # The test is considered passed if the numerical order of convergence
    # matches the expected order in at least the first step in the coarsest
    # spatial discretization, and is not getting worse as the spatial
    # discretizations are refining.
    assert (abs(orders['u'][:, 0] - MethodClass.order['velocity']) < 0.1).all()
    assert (abs(orders['p'][:, 0] - MethodClass.order['pressure']) < 0.1).all()
    return


def compute_time_errors(problem, MethodClass, mesh_sizes, Dt):

    mesh_generator, solution, f, mu, rho, cell_type = problem()
    # Translate data into FEniCS expressions.
    sol_u = Expression(
            (
                sympy.printing.ccode(solution['u']['value'][0]),
                sympy.printing.ccode(solution['u']['value'][1])
            ),
            degree=_truncate_degree(solution['u']['degree']),
            t=0.0,
            cell=cell_type
            )
    sol_p = Expression(
            sympy.printing.ccode(solution['p']['value']),
            degree=_truncate_degree(solution['p']['degree']),
            t=0.0,
            cell=cell_type
            )

    fenics_rhs0 = Expression(
            (
                sympy.printing.ccode(f['value'][0]),
                sympy.printing.ccode(f['value'][1])
            ),
            degree=_truncate_degree(f['degree']),
            t=0.0,
            mu=mu, rho=rho,
            cell=cell_type
            )
    # Deep-copy expression to be able to provide f0, f1 for the Dirichlet-
    # boundary conditions later on.
    fenics_rhs1 = Expression(fenics_rhs0.cppcode,
                             degree=_truncate_degree(f['degree']),
                             t=0.0,
                             mu=mu, rho=rho,
                             cell=cell_type
                             )
    # Create initial states.
    p0 = Expression(
        sol_p.cppcode,
        degree=_truncate_degree(solution['p']['degree']),
        t=0.0,
        cell=cell_type
        )

    # Compute the problem
    errors = {
        'u': numpy.empty((len(mesh_sizes), len(Dt))),
        'p': numpy.empty((len(mesh_sizes), len(Dt)))
        }
    for k, mesh_size in enumerate(mesh_sizes):
        mesh = mesh_generator(mesh_size)
        mesh_area = assemble(1.0 * dx(mesh))
        W = VectorFunctionSpace(mesh, 'CG', 2)
        P = FunctionSpace(mesh, 'CG', 1)
        method = MethodClass(
                W, P,
                rho, mu,
                theta=1.0,
                # theta=0.5,
                stabilization=None
                # stabilization='SUPG'
                )
        u1 = Function(W)
        p1 = Function(P)
        err_p = Function(P)
        divu1 = Function(P)
        for j, dt in enumerate(Dt):
            # Prepare previous states for multistepping.
            u = [Expression(
                sol_u.cppcode,
                degree=_truncate_degree(solution['u']['degree']),
                t=0.0,
                cell=cell_type
                ),
                # Expression(
                # sol_u.cppcode,
                # degree=_truncate_degree(solution['u']['degree']),
                # t=0.5*dt,
                # cell=cell_type
                # )
                ]
            sol_u.t = dt
            u_bcs = [DirichletBC(W, sol_u, 'on_boundary')]
            sol_p.t = dt
            # p_bcs = [DirichletBC(P, sol_p, 'on_boundary')]
            p_bcs = []
            fenics_rhs0.t = 0.0
            fenics_rhs1.t = dt
            method.step(dt,
                        u1, p1,
                        u, p0,
                        u_bcs=u_bcs, p_bcs=p_bcs,
                        f0=fenics_rhs0, f1=fenics_rhs1,
                        verbose=False,
                        tol=1.0e-10
                        )
            sol_u.t = dt
            sol_p.t = dt
            errors['u'][k][j] = errornorm(sol_u, u1)
            # The pressure is only determined up to a constant which makes
            # it a bit harder to define what the error is. For our
            # purposes, choose an alpha_0\in\R such that
            #
            #    alpha0 = argmin ||e - alpha||^2
            #
            # with  e := sol_p - p.
            # This alpha0 is unique and explicitly given by
            #
            #     alpha0 = 1/(2|Omega|) \int (e + e*)
            #            = 1/|Omega| \int Re(e),
            #
            # i.e., the mean error in \Omega.
            alpha = (
                + assemble(sol_p * dx(mesh))
                - assemble(p1 * dx(mesh))
                )
            alpha /= mesh_area
            # We would like to perform
            #     p1 += alpha.
            # To avoid creating a temporary function every time, assume
            # that p1 lives in a function space where the coefficients
            # represent actual function values. This is true for CG
            # elements, for example. In that case, we can just add any
            # number to the vector of p1.
            p1.vector()[:] += alpha
            errors['p'][k][j] = errornorm(sol_p, p1)

            show_plots = False
            if show_plots:
                plot(p1, title='p1', mesh=mesh)
                plot(sol_p, title='sol_p', mesh=mesh)
                err_p.vector()[:] = p1.vector()
                sol_interp = interpolate(sol_p, P)
                err_p.vector()[:] -= sol_interp.vector()
                # plot(sol_p - p1, title='p1 - sol_p', mesh=mesh)
                plot(err_p, title='p1 - sol_p', mesh=mesh)
                # r = Expression('x[0]', degree=1, cell=triangle)
                # divu1 = 1 / r * (r * u1[0]).dx(0) + u1[1].dx(1)
                divu1.assign(project(u1[0].dx(0) + u1[1].dx(1), P))
                plot(divu1, title='div(u1)')
    return errors
