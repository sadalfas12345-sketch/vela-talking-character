#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cstring>
#include <Eigen/Core>
#include <Eigen/Sparse>
#include <igl/arap.h>
#include <igl/cotmatrix.h>
#include <igl/columnize.h>
#include <igl/fit_rotations.h>
#include <igl/min_quad_with_fixed.h>
#include <igl/repdiag.h>

namespace py = pybind11;
using Matrix = Eigen::MatrixXd;
using IntMatrix = Eigen::MatrixXi;
using Vector = Eigen::VectorXd;

static Matrix copy_matrix(const py::array_t<double, py::array::c_style | py::array::forcecast>& a)
{
    auto b = a.request();
    if (b.ndim != 2) throw std::runtime_error("expected a rank-2 double array");
    Matrix out(b.shape[0], b.shape[1]);
    const auto* src = static_cast<const double*>(b.ptr);
    for (py::ssize_t r = 0; r < b.shape[0]; ++r)
        for (py::ssize_t c = 0; c < b.shape[1]; ++c)
            out(r, c) = src[r * b.shape[1] + c];
    return out;
}

static IntMatrix copy_int_matrix(const py::array_t<int, py::array::c_style | py::array::forcecast>& a)
{
    auto b = a.request();
    if (b.ndim != 2) throw std::runtime_error("expected a rank-2 int array");
    IntMatrix out(b.shape[0], b.shape[1]);
    const auto* src = static_cast<const int*>(b.ptr);
    for (py::ssize_t r = 0; r < b.shape[0]; ++r)
        for (py::ssize_t c = 0; c < b.shape[1]; ++c)
            out(r, c) = src[r * b.shape[1] + c];
    return out;
}

static Eigen::VectorXi copy_int_vector(const py::array_t<int, py::array::c_style | py::array::forcecast>& a)
{
    auto b = a.request();
    if (b.ndim != 1) throw std::runtime_error("expected a rank-1 int array");
    Eigen::VectorXi out(b.shape[0]);
    std::memcpy(out.data(), b.ptr, sizeof(int) * out.size());
    return out;
}

static bool solve_barycentric(
    const Matrix& V,
    const IntMatrix& F,
    const Eigen::VectorXi& b,
    const Matrix& Aeq,
    const Matrix& Beq,
    Matrix& U,
    const int max_iter)
{
    if (V.cols() != 3 || F.cols() != 3 || Aeq.cols() != V.rows() || Beq.rows() != Aeq.rows() || Beq.cols() != 3)
        throw std::runtime_error("invalid dimensions");

    igl::ARAPData data;
    data.energy = igl::ARAP_ENERGY_TYPE_ELEMENTS;
    data.max_iter = max_iter;
    if (!igl::arap_precomputation(V, F, 3, b, data)) return false;

    // This is the same quadratic matrix assembled by official arap_precomputation.
    Eigen::SparseMatrix<double> L;
    igl::cotmatrix(V, F, L);
    Eigen::SparseMatrix<double> Q = (-L).eval();
    Eigen::SparseMatrix<double> Aeq_sparse = Aeq.sparseView();
    if (!igl::min_quad_with_fixed_precompute(Q, b, Aeq_sparse, true, data.solver_data)) return false;

    const int n = data.n;
    Matrix U_prev = U;
    int iter = 0;
    while (iter < data.max_iter)
    {
        U_prev = U;
        for (int bi = 0; bi < b.size(); ++bi) U.row(b(bi)) = U_prev.row(b(bi));

        const auto Udim = U.replicate(data.dim, 1);
        Matrix S = data.CSM * Udim;
        const double scale = S.array().abs().maxCoeff();
        if (scale > 0) S /= scale;
        Matrix R(data.dim, data.CSM.rows());
        igl::fit_rotations(S, true, R);

        const int num_rots = static_cast<int>(data.K.cols() / data.dim / data.dim);
        Matrix eff_R = R;
        if (data.G.size() != 0)
        {
            eff_R.resize(data.dim, num_rots * data.dim);
            for (int r = 0; r < num_rots; ++r)
                eff_R.block(0, data.dim * r, data.dim, data.dim) = R.block(0, data.dim * data.G(r), data.dim, data.dim);
        }

        Vector Rcol;
        igl::columnize(eff_R, num_rots, 2, Rcol);
        Vector Bcol = -data.K * Rcol;
        for (int c = 0; c < data.dim; ++c)
        {
            Vector Bc = Bcol.block(c * n, 0, n, 1);
            Vector bcc = Vector::Zero(b.size());
            for (int i = 0; i < b.size(); ++i) bcc(i) = U(b(i), c);
            Vector beqc = Beq.col(c);
            Vector Uc;
            if (!igl::min_quad_with_fixed_solve(data.solver_data, Bc, bcc, beqc, Uc)) return false;
            U.col(c) = Uc;
        }
        ++iter;
    }
    return true;
}

PYBIND11_MODULE(libigl_barycentric_bridge, m)
{
    m.def("solve", [](py::array_t<double, py::array::c_style | py::array::forcecast> v,
                       py::array_t<int, py::array::c_style | py::array::forcecast> f,
                       py::array_t<int, py::array::c_style | py::array::forcecast> b,
                       py::array_t<double, py::array::c_style | py::array::forcecast> aeq,
                       py::array_t<double, py::array::c_style | py::array::forcecast> beq,
                       py::array_t<double, py::array::c_style | py::array::forcecast> initial,
                       int max_iter) {
        Matrix V = copy_matrix(v);
        IntMatrix F = copy_int_matrix(f);
        Eigen::VectorXi B = copy_int_vector(b);
        Matrix A = copy_matrix(aeq);
        Matrix C = copy_matrix(beq);
        Matrix U = copy_matrix(initial);
        if (!solve_barycentric(V, F, B, A, C, U, max_iter)) throw std::runtime_error("libigl constrained ARAP failed");
        py::array_t<double> out({static_cast<py::ssize_t>(U.rows()), static_cast<py::ssize_t>(U.cols())});
        auto ob = out.request();
        auto* dst = static_cast<double*>(ob.ptr);
        for (py::ssize_t r = 0; r < U.rows(); ++r)
            for (py::ssize_t c = 0; c < U.cols(); ++c)
                dst[r * U.cols() + c] = U(r, c);
        return out;
    }, py::arg("V"), py::arg("F"), py::arg("b"), py::arg("Aeq"), py::arg("Beq"), py::arg("initial"), py::arg("max_iter") = 50);
}


